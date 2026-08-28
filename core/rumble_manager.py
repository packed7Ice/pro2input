"""
core/rumble_manager.py

Converts Xbox 360 force-feedback (large_motor, small_motor) into
Switch 2 Pro Controller HD Rumble 2 packets and sends them via
Interface 0 Interrupt OUT (ep 0x01).

Key behavior: the controller requires CONTINUOUS packet delivery to keep
motors spinning.  A single packet is not latched — if packets stop, the
motor stops within ~100ms.  drain_and_send() must be called periodically
(every ~1ms from the main loop) and will re-transmit the current rumble
state every RUMBLE_INTERVAL (12ms), matching SDL's UpdateRumble cadence.
"""

import threading
import time

from core.constants import (
    SWITCH2_RUMBLE_REPORT_ID,
    RUMBLE_NEUTRAL_ACTUATOR,
    RUMBLE_HF_FREQ,
    RUMBLE_LF_FREQ,
    RUMBLE_AMP_MAX,
)

RUMBLE_INTERVAL_SEC = 0.012  # SDL RUMBLE_INTERVAL: 12ms between packets


class RumbleManager:
    """
    Thread-safe rumble manager.

    send_rumble(large, small) - called from any thread to set desired state.
    drain_and_send()          - called from the main loop every ~1ms; sends
                                a packet every RUMBLE_INTERVAL when active.
    """

    def __init__(self, usb_controller, strength: float = 1.0):
        self.usb = usb_controller
        self._strength = max(0.0, min(strength, 2.0))
        self._lock = threading.Lock()
        self._seq = 0

        # Desired rumble state (set by send_rumble, read by drain_and_send)
        self._active_large = 0
        self._active_small = 0

        # Last physically sent values (to detect transition to zero for neutral packet)
        self._sent_large = 0
        self._sent_small = 0

        self._rumble_fail_count = 0

        self._last_send_time = 0.0

        # When True, ignore XInput callbacks (used when FH6 UDP is active)
        self.ignore_xinput = False

    def start(self):
        pass

    def stop(self):
        """Silence motors and reset active state so drain_and_send() doesn't restart them."""
        with self._lock:
            self._active_large = 0
            self._active_small = 0
        self._send_packet(self._build_neutral_packet())
        self._sent_large = 0
        self._sent_small = 0

    def drain_and_send(self):
        """
        Must be called periodically from the main loop (~every 1ms).
        Sends the current rumble state every RUMBLE_INTERVAL (12ms).
        If rumble drops to zero, sends one neutral packet to silence motors.
        """
        now = time.time()
        if now - self._last_send_time < RUMBLE_INTERVAL_SEC:
            return

        with self._lock:
            large = self._active_large
            small = self._active_small

        if large != 0 or small != 0:
            self._send_packet(self._build_rumble_packet(large, small))
            self._sent_large = large
            self._sent_small = small
        elif self._sent_large != 0 or self._sent_small != 0:
            # State just changed to zero — send one neutral to stop motors
            self._send_packet(self._build_neutral_packet())
            self._sent_large = 0
            self._sent_small = 0
        else:
            return  # Nothing to do

        self._last_send_time = now

    def get_intensity(self) -> tuple[float, float]:
        """Return (large, small) as 0.0-1.0, for status/UI display only."""
        with self._lock:
            return self._active_large / 255.0, self._active_small / 255.0

    def set_strength(self, value: float):
        """Update the overall rumble multiplier live. Thread-safe."""
        with self._lock:
            self._strength = max(0.0, min(value, 2.0))

    def send_rumble(self, large_motor: int, small_motor: int):
        """
        Set the desired rumble state.  Thread-safe.
        Values are 0-255 per XInput convention.
        The state is picked up by drain_and_send() on the next cycle.
        """
        large_motor = max(0, min(255, int(large_motor)))
        small_motor = max(0, min(255, int(small_motor)))
        with self._lock:
            self._active_large = large_motor
            self._active_small = small_motor

    def on_xinput_rumble(self, client, target, large_motor, small_motor, led_number, user_data):
        """Callback for vgamepad.VX360Gamepad.register_notification()."""
        if self.ignore_xinput:
            return
        self.send_rumble(large_motor, small_motor)

    def _build_rumble_packet(self, large_motor: int, small_motor: int) -> bytes:
        hf_amp = int((small_motor / 255.0) * RUMBLE_AMP_MAX * self._strength)
        lf_amp = int((large_motor / 255.0) * RUMBLE_AMP_MAX * self._strength)
        hf_amp = min(hf_amp, RUMBLE_AMP_MAX)
        lf_amp = min(lf_amp, RUMBLE_AMP_MAX)
        actuator = self._encode_actuator(RUMBLE_HF_FREQ, hf_amp, RUMBLE_LF_FREQ, lf_amp)
        return self._build_report(actuator)

    def _build_neutral_packet(self) -> bytes:
        return self._build_report(RUMBLE_NEUTRAL_ACTUATOR)

    def _build_report(self, actuator: bytes) -> bytes:
        """
        64-byte HID Output Report layout (SDL-verified):
          [0]     = 0x02 (Report ID)
          [1]     = 0x50 | (seq & 0x0F)
          [2:7]   = left actuator (5 bytes)
          [17:23] = copy of [1:7] — SDL: memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)
        """
        self._seq = (self._seq + 1) & 0x0F
        seq_byte = 0x50 | self._seq

        report = bytearray(64)
        report[0] = SWITCH2_RUMBLE_REPORT_ID  # 0x02
        report[1] = seq_byte
        report[2:7] = actuator
        report[17:23] = report[1:7]  # SDL: 0x11 = 17 decimal
        return bytes(report)

    @staticmethod
    def _encode_actuator(high_freq: int, high_amp: int, low_freq: int, low_amp: int) -> bytes:
        """SDL EncodeHDRumble: 5-byte HD Rumble 2 actuator encoding."""
        data = bytearray(5)
        data[0] = high_freq & 0xFF
        data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
        data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
        data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
        data[4] = (low_amp >> 8) & 0xFF
        return bytes(data)

    def _send_packet(self, packet: bytes):
        try:
            self.usb.send_rumble_bulk(packet)
        except Exception:
            pass
