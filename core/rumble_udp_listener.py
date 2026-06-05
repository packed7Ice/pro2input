"""
core/rumble_udp_listener.py

Receives FH6 Data Out (UDP telemetry) and drives the RumbleManager
directly, bypassing the XInput callback path.
"""

import socket
import struct
import threading
import time
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Packet field offsets (bytes, little-endian)
# ---------------------------------------------------------------------------
_OFF_IS_RACE_ON = 0               # s32
_OFF_SURFACE_RUMBLE_FL = 148      # f32
_OFF_SURFACE_RUMBLE_FR = 152
_OFF_SURFACE_RUMBLE_RL = 156
_OFF_SURFACE_RUMBLE_RR = 160
_OFF_TIRE_COMBINED_SLIP_FL = 180  # f32
_OFF_TIRE_COMBINED_SLIP_FR = 184
_OFF_TIRE_COMBINED_SLIP_RL = 188
_OFF_TIRE_COMBINED_SLIP_RR = 192
_OFF_SMASHABLE_VEL_DIFF = 236     # f32

_PACKET_SIZE = 324


class FH6RumbleUDPListener(threading.Thread):
    """
    Background thread that listens for FH6 UDP telemetry on a given port
    and translates surface rumble / slip / smashable events into motor
    intensities for RumbleManager.
    """

    def __init__(
        self,
        rumble_manager,
        port: int = 5301,
        strength: float = 1.0,
        smashable_threshold: float = 3.0,
        slip_scale: float = 0.8,
        surface_scale: float = 1.0,
        timeout_ms: int = 300,
        hold_ms: int = 150,
    ):
        super().__init__(daemon=True, name="FH6UDPListener")
        self.rumble_manager = rumble_manager
        self.port = port
        self.strength = max(0.0, min(strength, 2.0))
        self.smashable_threshold = smashable_threshold
        self.slip_scale = slip_scale
        self.surface_scale = surface_scale
        self.timeout_sec = timeout_ms / 1000.0
        self._hold_sec = hold_ms / 1000.0  # sustain rumble this long after drop to zero

        self._sock: socket.socket | None = None
        self._running = False
        self._last_packet_time = 0.0
        self._timed_out = True
        self._last_log_time = 0.0

        # Hold state: keep last non-zero rumble for _hold_sec after value drops to zero
        self._hold_large = 0
        self._hold_small = 0
        self._hold_until = 0.0

    def start(self):
        self._running = True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(0.1)
            self._sock.bind(("0.0.0.0", self.port))
            logger.info("FH6 UDP listener bound to port %d", self.port)
        except OSError as exc:
            logger.error("Failed to bind UDP socket on port %d: %s", self.port, exc)
            self._running = False
            self._sock = None
            raise
        super().start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self.join(timeout=1.0)

    def run(self):
        while self._running:
            try:
                data, _addr = self._sock.recvfrom(_PACKET_SIZE)
            except socket.timeout:
                self._check_timeout()
                continue
            except OSError:
                # Socket closed or other error
                break

            if len(data) < _PACKET_SIZE:
                continue

            self._last_packet_time = time.time()
            self._timed_out = False
            self._process_packet(data)

        # On exit, silence motors if we were driving them
        if not self._timed_out:
            self.rumble_manager.send_rumble(0, 0)

    def _check_timeout(self):
        if self._timed_out:
            return
        if time.time() - self._last_packet_time > self.timeout_sec:
            self._timed_out = True
            self.rumble_manager.send_rumble(0, 0)

    def _process_packet(self, data: bytes):
        # IsRaceOn (s32) at offset 0
        is_race_on = struct.unpack_from("<i", data, _OFF_IS_RACE_ON)[0]
        if is_race_on == 0:
            self._hold_large = 0
            self._hold_small = 0
            self._hold_until = 0.0
            self.rumble_manager.send_rumble(0, 0)
            return

        # Surface rumble (4x f32)
        rumble_fl = struct.unpack_from("<f", data, _OFF_SURFACE_RUMBLE_FL)[0]
        rumble_fr = struct.unpack_from("<f", data, _OFF_SURFACE_RUMBLE_FR)[0]
        rumble_rl = struct.unpack_from("<f", data, _OFF_SURFACE_RUMBLE_RL)[0]
        rumble_rr = struct.unpack_from("<f", data, _OFF_SURFACE_RUMBLE_RR)[0]
        max_surface = max(rumble_fl, rumble_fr, rumble_rl, rumble_rr)

        # Tire combined slip (4x f32, absolute)
        slip_fl = abs(struct.unpack_from("<f", data, _OFF_TIRE_COMBINED_SLIP_FL)[0])
        slip_fr = abs(struct.unpack_from("<f", data, _OFF_TIRE_COMBINED_SLIP_FR)[0])
        slip_rl = abs(struct.unpack_from("<f", data, _OFF_TIRE_COMBINED_SLIP_RL)[0])
        slip_rr = abs(struct.unpack_from("<f", data, _OFF_TIRE_COMBINED_SLIP_RR)[0])
        max_slip = max(slip_fl, slip_fr, slip_rl, slip_rr)

        # Smashable velocity difference (f32)
        smash = struct.unpack_from("<f", data, _OFF_SMASHABLE_VEL_DIFF)[0]

        # -----------------------------------------------------------------
        # Rumble intensity calculation
        # -----------------------------------------------------------------
        large = 0   # low-frequency motor
        small = 0   # high-frequency motor

        # 1. Collision (highest priority)
        if smash > self.smashable_threshold:
            intensity = min(1.0, smash / 15.0)  # clamp at 15 m/s
            val = int(intensity * 255 * self.strength)
            val = max(0, min(255, val))
            large = val
            small = val
        else:
            # 2. Slip -> high-frequency motor
            # max_slip is often >1 when losing grip; clamp and scale
            slip_val = min(1.0, max_slip) * self.slip_scale
            small = int(slip_val * 255 * self.strength)
            small = max(0, min(255, small))

            # 3. Surface rumble -> low-frequency motor
            surface_val = min(1.0, max_surface) * self.surface_scale
            large = int(surface_val * 255 * self.strength)
            large = max(0, min(255, large))

        now = time.time()

        # Hold: keep last non-zero rumble for _hold_sec to smooth out brief dips to zero
        if large != 0 or small != 0:
            self._hold_large = large
            self._hold_small = small
            self._hold_until = now + self._hold_sec
        elif now < self._hold_until:
            large = self._hold_large
            small = self._hold_small

        self.rumble_manager.send_rumble(large, small)

        if now - self._last_log_time >= 1.0:
            self._last_log_time = now
            print(
                f"[FH6-UDP] RaceOn={is_race_on}  "
                f"Surface={max_surface:.3f}  Slip={max_slip:.3f}  "
                f"Smash={smash:.2f}  ->  Rumble(large={large}, small={small})"
            )
