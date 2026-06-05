"""
core/rumble_manager.py

Converts Xbox 360 force-feedback (large_motor, small_motor) into
Switch 2 Pro Controller HD Rumble 2 packets and sends them via Interface 1 Bulk OUT.

Based on SDL's official implementation:
  libsdl-org/SDL/src/joystick/hidapi/SDL_hidapi_switch2.c

Key differences from original Switch Pro Controller:
  - Report ID: 0x02 (not 0x10/0x01)
  - Transport: Interface 1 Bulk OUT (not HID Output Report)
  - Packet size: exactly 64 bytes
  - Actuator encoding: 5 bytes each with different bit packing
"""

import queue
import threading
import time

from core.constants import (
    SWITCH2_RUMBLE_REPORT_ID,
    RUMBLE_NEUTRAL_ACTUATOR,
    RUMBLE_HF_FREQ,
    RUMBLE_LF_FREQ,
    RUMBLE_AMP_MAX,
)

# SDL's RUMBLE_INTERVAL: minimum 12ms between packets
RUMBLE_INTERVAL_SEC = 0.012


class RumbleManager:
    """
    Thread-safe rumble manager.

    - Receives (large_motor, small_motor) values from vgamepad callbacks
      or from the UDP telemetry listener.
    - Queues packets; the caller (main.py input loop) is responsible for
      calling drain_and_send() on the main thread to avoid USB contention.
    - Throttles sends to RUMBLE_INTERVAL (12ms) to prevent USB pipe errors.
    - Sends neutral packets when no command is pending to silence motors.
    """

    def __init__(self, usb_controller, strength: float = 1.0):
        self.usb = usb_controller
        self._strength = max(0.0, min(strength, 2.0))
        self._lock = threading.Lock()
        self._seq = 0
        self._queue: queue.Queue[bytes] = queue.Queue()

        # Track last sent values to avoid duplicate writes
        self._last_sent_large = 0
        self._last_sent_small = 0

        # Throttle sends to prevent USB pipe errors
        self._last_send_time = 0.0
        self._pending_packet: bytes | None = None

        # When True, ignore XInput callbacks (used when FH6 UDP is active)
        self.ignore_xinput = False

    def start(self):
        """No-op: USB writes are driven by the caller's main loop."""
        pass

    def stop(self):
        """Silence motors on shutdown."""
        self._send_packet(self._build_neutral_packet())

    def drain_and_send(self):
        """
        Must be called periodically (e.g. inside the main input loop).
        Drains the queue and sends the latest packet, throttled to
        RUMBLE_INTERVAL (12ms). Also sends a neutral packet if no new
        command arrived and motors are active.
        """
        # Gather the latest queued value
        latest_packet = None
        while not self._queue.empty():
            try:
                latest_packet = self._queue.get_nowait()
            except queue.Empty:
                break

        if latest_packet is not None:
            self._pending_packet = latest_packet

        # Throttle: only send every 12ms (SDL's RUMBLE_INTERVAL)
        now = time.time()
        if now - self._last_send_time < RUMBLE_INTERVAL_SEC:
            return  # Too soon; keep _pending_packet for next cycle

        if self._pending_packet is not None:
            self._send_packet(self._pending_packet)
            self._pending_packet = None
            self._last_send_time = now
        else:
            # No new command: silence if motors are still active
            if self._last_sent_large != 0 or self._last_sent_small != 0:
                self._send_packet(self._build_neutral_packet())
                self._last_sent_large = 0
                self._last_sent_small = 0
                self._last_send_time = now

    def send_rumble(self, large_motor: int, small_motor: int):
        """
        Public API to queue a rumble command.
        Values are 0-255 per XInput convention.
        Only the latest queued command per drain_and_send() call is sent.
        """
        large_motor = max(0, min(255, int(large_motor)))
        small_motor = max(0, min(255, int(small_motor)))
        if large_motor != self._last_sent_large or small_motor != self._last_sent_small:
            packet = self._build_rumble_packet(large_motor, small_motor)
            self._queue.put_nowait(packet)
            self._last_sent_large = large_motor
            self._last_sent_small = small_motor

    def on_xinput_rumble(self, client, target, large_motor, small_motor, led_number, user_data):
        """
        Callback signature for vgamepad.VX360Gamepad.register_notification().
        Receives force-feedback events from the game/OS.
        """
        if self.ignore_xinput:
            return
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
        """Assemble the 64-byte report layout with the given actuator data."""
        self._seq = (self._seq + 1) & 0x0F
        seq_byte = 0x50 | self._seq

        report = bytearray(64)
        report[0] = SWITCH2_RUMBLE_REPORT_ID   # 0x02
        report[1] = seq_byte
        report[2:7] = actuator                   # left actuator (5 bytes)
        # Copy seq + actuator to [11:16] (tested working pattern)
        report[11:17] = report[1:7]              # copy seq + actuator

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

    def _send_packet(self, packet: bytes):
        """Send the 64-byte rumble packet via Interface 1 Bulk OUT."""
        try:
            ok = self.usb.send_rumble_bulk(packet)
            if not ok:
                pass  # Silent: errors are already printed by controller_usb
        except Exception:
            pass  # Silent: avoid spamming console on transient USB errors
