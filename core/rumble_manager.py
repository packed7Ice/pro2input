"""
core/rumble_manager.py

Converts Xbox 360 force-feedback (large_motor, small_motor) into
Switch 2 Pro Controller HD Rumble packets and sends them via HID Output Report.

Based on SDL's official implementation:
  libsdl-org/SDL/src/joystick/hidapi/SDL_hidapi_switch2.c

Key differences from original Switch Pro Controller:
  - Report ID: 0x02 (not 0x10/0x01)
  - Transport: HID Output Report via ctrl_transfer (not Bulk OUT)
  - Packet size: exactly 64 bytes
  - Actuator encoding: 5 bytes each with different bit packing
"""

import time
import threading
import queue

from core.constants import (
    SWITCH2_RUMBLE_REPORT_ID,
    RUMBLE_NEUTRAL_ACTUATOR,
    RUMBLE_HF_FREQ,
    RUMBLE_LF_FREQ,
    RUMBLE_AMP_MAX,
)


class RumbleManager:
    """
    Thread-safe rumble manager.

    - Receives (large_motor, small_motor) values from vgamepad callbacks.
    - Builds 64-byte Switch 2 Pro HID Output Reports.
    - Queues packets for the background sender thread.
    """

    def __init__(self, usb_controller):
        self.usb = usb_controller
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._latest_large = 0
        self._latest_small = 0
        self._lock = threading.Lock()
        self._sender_thread: threading.Thread | None = None
        self._running = False
        self._seq = 0

    def start(self):
        """Start the background sender thread."""
        self._running = True
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

    def stop(self):
        """Stop the sender thread."""
        self._running = False
        if self._sender_thread:
            self._sender_thread.join(timeout=1.0)

    def on_xinput_rumble(self, client, target, large_motor, small_motor, led_number, user_data):
        """
        Callback signature for vgamepad.VX360Gamepad.register_notification().
        Receives force-feedback events from the game/OS.
        """
        with self._lock:
            self._latest_large = large_motor
            self._latest_small = small_motor
        # Build a packet and queue it (drop old packet if queue is full)
        packet = self._build_rumble_packet(large_motor, small_motor)
        try:
            self._queue.put_nowait(packet)
        except queue.Full:
            pass

    def _build_rumble_packet(self, large_motor: int, small_motor: int) -> bytes:
        """
        Build a 64-byte Switch 2 Pro HID Output Report for rumble.

        SDL maps:
        - large_motor (0-255) -> Low  frequency amplitude
        - small_motor (0-255) -> High frequency amplitude
        """
        hf_amp = int((small_motor / 255.0) * RUMBLE_AMP_MAX)
        lf_amp = int((large_motor / 255.0) * RUMBLE_AMP_MAX)
        hf_amp = min(hf_amp, RUMBLE_AMP_MAX)
        lf_amp = min(lf_amp, RUMBLE_AMP_MAX)

        actuator = self._encode_actuator(RUMBLE_HF_FREQ, hf_amp, RUMBLE_LF_FREQ, lf_amp)
        return self._build_report(actuator)

    def _build_neutral_packet(self) -> bytes:
        """Build a 64-byte neutral (no vibration) report."""
        return self._build_report(RUMBLE_NEUTRAL_ACTUATOR)

    def _build_report(self, actuator: bytes) -> bytes:
        """Assemble the common 64-byte report layout with the given actuator data."""
        self._seq = (self._seq + 1) & 0x0F
        seq_byte = 0x50 | self._seq

        report = bytearray(64)
        report[0] = SWITCH2_RUMBLE_REPORT_ID   # 0x02
        report[1] = seq_byte
        report[2:7] = actuator                   # left actuator (5 bytes)
        # bytes 7-16: padding (already 0x00)
        report[17] = seq_byte                    # sequence copy
        report[18:23] = actuator                 # right actuator (often same as left)
        # bytes 23-63: padding (already 0x00)

        return bytes(report)

    @staticmethod
    def _encode_actuator(high_freq: int, high_amp: int, low_freq: int, low_amp: int) -> bytes:
        """
        Encode one actuator (5 bytes) per SDL's EncodeHDRumble.

        SDL source (C):
            rumble_data[0] = (Uint8)(high_freq & 0xFF);
            rumble_data[1] = (Uint8)(((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03));
            rumble_data[2] = (Uint8)((high_amp >> 12) | (low_freq << 4));
            rumble_data[3] = (Uint8)((low_amp & 0xC0) | ((low_freq >> 4) & 0x3F));
            rumble_data[4] = (Uint8)(low_amp >> 8);
        """
        data = bytearray(5)
        data[0] = high_freq & 0xFF
        data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
        data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
        data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
        data[4] = (low_amp >> 8) & 0xFF
        return bytes(data)

    def _sender_loop(self):
        """
        Background thread: dequeue rumble packets and send them to the controller.
        Sends a neutral packet when no rumble is active to silence the motors.
        """
        last_was_neutral = True
        while self._running:
            try:
                packet = self._queue.get(timeout=0.05)
            except queue.Empty:
                packet = None

            if packet:
                self._send_packet(packet)
                last_was_neutral = False
            else:
                # If no new rumble command, and motors were active, send neutral
                if not last_was_neutral:
                    self._send_packet(self._build_neutral_packet())
                    last_was_neutral = True

            time.sleep(0.01)

    def _send_packet(self, packet: bytes):
        """Send the 64-byte HID Output Report via Interface 0 Interrupt OUT."""
        self.usb.write_output_report(packet)
