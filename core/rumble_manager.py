"""
core/rumble_manager.py

Converts Xbox 360 force-feedback (large_motor, small_motor) into
Switch 2 Pro Controller HD Rumble 2 packets and sends them via HID Output Report.

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

    - Receives (large_motor, small_motor) values from vgamepad callbacks
      or from the UDP telemetry listener.
    - Keeps only the latest command; background sender sends it at ~200 Hz.
    - Sends neutral packets when no command is pending to silence motors.
    """

    def __init__(self, usb_controller, strength: float = 1.0):
        self.usb = usb_controller
        self._strength = max(0.0, min(strength, 2.0))
        self._lock = threading.Lock()
        self._sender_thread: threading.Thread | None = None
        self._running = False
        self._seq = 0

        # Latest pending command (set by callers, consumed by sender thread)
        self._pending = False
        self._pending_large = 0
        self._pending_small = 0

        # Last actually-sent values (for duplicate suppression and neutral logic)
        self._last_sent_large = 0
        self._last_sent_small = 0

    def start(self):
        """Start the background sender thread."""
        self._running = True
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

    def stop(self):
        """Stop the sender thread."""
        self._running = False
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=1.0)

    def send_rumble(self, large_motor: int, small_motor: int):
        """
        Public API to send a rumble command directly (e.g. from UDP listener).
        Values are 0-255 per XInput convention.
        Only the latest call is kept; older values are overwritten.
        """
        large_motor = max(0, min(255, int(large_motor)))
        small_motor = max(0, min(255, int(small_motor)))
        with self._lock:
            self._pending_large = large_motor
            self._pending_small = small_motor
            self._pending = True

    def on_xinput_rumble(self, client, target, large_motor, small_motor, led_number, user_data):
        """
        Callback signature for vgamepad.VX360Gamepad.register_notification().
        Receives force-feedback events from the game/OS.
        """
        self.send_rumble(large_motor, small_motor)

    def _build_rumble_packet(self, large_motor: int, small_motor: int) -> bytes:
        """
        Build a 64-byte Switch 2 Pro HID Output Report for rumble.

        SDL maps:
        - large_motor (0-255) -> Low  frequency amplitude
        - small_motor (0-255) -> High frequency amplitude
        """
        hf_amp = int((small_motor / 255.0) * RUMBLE_AMP_MAX * self._strength)
        lf_amp = int((large_motor / 255.0) * RUMBLE_AMP_MAX * self._strength)
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
        report[17] = seq_byte                    # sequence copy
        report[18:23] = actuator                 # right actuator (often same as left)

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
        Background thread: polls the latest pending command and sends it.
        Falls back to neutral packets when nothing is pending.
        Runs at ~200 Hz to keep up with high-frequency UDP telemetry.
        """
        while self._running:
            with self._lock:
                has_pending = self._pending
                if has_pending:
                    large = self._pending_large
                    small = self._pending_small
                    self._pending = False
                else:
                    large = 0
                    small = 0

            if has_pending:
                if large != self._last_sent_large or small != self._last_sent_small:
                    packet = self._build_rumble_packet(large, small)
                    self._send_packet(packet)
                    self._last_sent_large = large
                    self._last_sent_small = small
            else:
                # No new command: if motors are still active, send neutral
                if self._last_sent_large != 0 or self._last_sent_small != 0:
                    self._send_packet(self._build_neutral_packet())
                    self._last_sent_large = 0
                    self._last_sent_small = 0

            time.sleep(0.005)

    def _send_packet(self, packet: bytes):
        """Send the 64-byte HID Output Report via Interface 0 Interrupt OUT."""
        self.usb.write_output_report(packet)
