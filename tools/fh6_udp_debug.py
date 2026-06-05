"""
tools/fh6_udp_debug.py

Standalone UDP telemetry receiver for FH6.
Prints key fields from every packet so you can verify:
  1. The game is actually sending UDP data
  2. The IP/port settings match
  3. IsRaceOn flips to 1 when driving
  4. SurfaceRumble / Slip / Smashable values are non-zero

Usage:
    python tools/fh6_udp_debug.py [PORT]

Default port is 5301 (matches config.json).
Press Ctrl+C to stop.
"""

import sys
import socket
import struct
import time

_PACKET_SIZE = 324

# Offsets
_OFF_IS_RACE_ON = 0
_OFF_SURFACE_RUMBLE_FL = 148
_OFF_TIRE_COMBINED_SLIP_FL = 180
_OFF_SMASHABLE_VEL_DIFF = 236
_OFF_ACCEL = 315
_OFF_BRAKE = 316
_OFF_SPEED = 256


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5301

    print("=" * 70)
    print(" FH6 UDP Telemetry Debug")
    print("=" * 70)
    print(f"[INFO] Listening on UDP port {port}...")
    print("[INFO] Start FH6, go to Settings → HUD and Gameplay → Data Out → ON")
    print("       Set IP to 127.0.0.1 and port to", port)
    print("[INFO] Begin driving.  Packets should appear below.\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as exc:
        print(f"[FATAL] Cannot bind port {port}: {exc}")
        sys.exit(1)

    packet_count = 0
    last_summary = 0.0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(_PACKET_SIZE)
            except socket.timeout:
                continue

            if len(data) < _PACKET_SIZE:
                print(f"[WARN] Short packet ({len(data)} bytes) from {addr}")
                continue

            packet_count += 1
            is_race_on = struct.unpack_from("<i", data, _OFF_IS_RACE_ON)[0]
            surface_fl = struct.unpack_from("<f", data, _OFF_SURFACE_RUMBLE_FL)[0]
            slip_fl = abs(struct.unpack_from("<f", data, _OFF_TIRE_COMBINED_SLIP_FL)[0])
            smash = struct.unpack_from("<f", data, _OFF_SMASHABLE_VEL_DIFF)[0]
            speed = struct.unpack_from("<f", data, _OFF_SPEED)[0]
            accel = struct.unpack_from("<B", data, _OFF_ACCEL)[0]
            brake = struct.unpack_from("<B", data, _OFF_BRAKE)[0]

            now = time.time()
            if now - last_summary >= 0.5:
                last_summary = now
                print(
                    f"[Pkt {packet_count:4d}] RaceOn={is_race_on}  "
                    f"Speed={speed:5.1f}  Accel={accel:3d}  Brake={brake:3d}  "
                    f"Surface={surface_fl:.3f}  Slip={slip_fl:.3f}  Smash={smash:.2f}"
                )
    except KeyboardInterrupt:
        print(f"\n[INFO] Stopped.  Total packets: {packet_count}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
