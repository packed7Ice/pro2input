"""
core/rumble_manager.py

Converts Xbox 360 force-feedback (large_motor, small_motor) into
Switch Pro Controller HD Rumble data and sends it over USB.

NOTE:
- This is an experimental implementation. Switch 2 Pro's exact rumble
  command format is not yet publicly documented.
- We reuse the original Nintendo Switch Pro Controller rumble protocol
  (subcommand 0x10 / 0x01 with 8-byte rumble data) as a best-effort
  translation. HD Rumble's full waveform control is not possible
  because XInput only provides two intensity values (0-255).
- Safe amplitude limits are enforced to protect linear actuators.
"""

import time
import threading
import queue

from core.constants import (
    RUMBLE_NEUTRAL,
    RUMBLE_HF_AMP_MAX,
    RUMBLE_LF_AMP_MAX,
)


class RumbleManager:
    """
    Thread-safe rumble manager.

    - Receives (large_motor, small_motor) values from vgamepad callbacks.
    - Converts them to Switch Pro rumble data packets.
    - Queues packets for the USB sender thread.
    """

    def __init__(self, usb_controller):
        self.usb = usb_controller
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._latest_large = 0
        self._latest_small = 0
        self._lock = threading.Lock()
        self._sender_thread: threading.Thread | None = None
        self._running = False

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
        Build an 8-byte rumble data block for left/right linear actuators.

        Mapping:
        - large_motor (0-255)  -> Low Frequency amplitude (left & right)
        - small_motor (0-255)  -> High Frequency amplitude (left & right)

        We use a fixed frequency pair for simplicity and safety.
        """
        # Scale 0-255 into safe amplitude ranges
        lf_amp = int(0x40 + (large_motor / 255.0) * (RUMBLE_LF_AMP_MAX - 0x40))
        hf_amp = int((small_motor / 255.0) * RUMBLE_HF_AMP_MAX)

        # Clamp for safety
        lf_amp = min(lf_amp, RUMBLE_LF_AMP_MAX)
        hf_amp = min(hf_amp, RUMBLE_HF_AMP_MAX)

        # Fixed frequencies (safe defaults)
        hf_freq = 0x0074  # ~600 Hz
        lf_freq = 0x5C     # ~260 Hz

        # Left actuator rumble data (4 bytes)
        left = self._encode_rumble(hf_freq, hf_amp, lf_freq, lf_amp)
        # Right actuator rumble data (4 bytes)
        right = self._encode_rumble(hf_freq, hf_amp, lf_freq, lf_amp)

        return left + right

    @staticmethod
    def _encode_rumble(hf_freq: int, hf_amp: int, lf_freq: int, lf_amp: int) -> bytes:
        """
        Encode one actuator (4 bytes) based on Nintendo Switch Pro format.

        Bytes:
        0-1: High frequency (little-endian-ish packed) + amplitude
        2-3: Low frequency + amplitude
        """
        # HF: byte0 = freq_low, byte1 = amp + freq_high
        byte0 = hf_freq & 0xFF
        byte1 = hf_amp + ((hf_freq >> 8) & 0xFF)

        # LF: byte2 = freq + amp_high, byte3 = amp_low
        lf_amp_word = (lf_amp << 8) | 0x40
        byte2 = lf_freq + ((lf_amp_word >> 8) & 0xFF)
        byte3 = lf_amp_word & 0xFF

        return bytes([byte0, byte1, byte2, byte3])

    def _sender_loop(self):
        """
        Background thread: dequeue rumble packets and send them to the controller.
        Sends a neutral packet when no rumble is active to silence the motors.
        """
        last_packet = RUMBLE_NEUTRAL
        while self._running:
            try:
                packet = self._queue.get(timeout=0.05)
            except queue.Empty:
                packet = None

            if packet:
                last_packet = packet
                self._send_rumble(packet)
            else:
                # If no new rumble command, and motors were active, send neutral
                # to stop vibration when the game stops requesting it.
                if last_packet != RUMBLE_NEUTRAL:
                    self._send_rumble(RUMBLE_NEUTRAL)
                    last_packet = RUMBLE_NEUTRAL

            time.sleep(0.01)

    def _send_rumble(self, rumble_data: bytes):
        """
        Send rumble data to the Switch 2 Pro Controller via Interface 1 Bulk OUT.

        Command format (experimental):
        [0x10, 0x91, 0x00, timer, ...rumble_data...]
        We reuse the original Switch Pro Controller's OUTPUT 0x10 prefix.
        If Switch 2 uses a different format, this packet may be ignored by the device.
        """
        # Timer byte: simple incrementing counter (0x00-0x0F loops)
        timer = int(time.time() * 100) & 0x0F
        cmd = bytes([0x10, 0x91, 0x00, timer]) + rumble_data
        self.usb.send_command(cmd)
