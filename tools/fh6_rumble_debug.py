"""
tools/fh6_rumble_debug.py

Captures and logs all force-feedback (rumble) events received by the
virtual gamepad.  Supports both Xbox 360 (VX360Gamepad) and DualShock 4
(VDS4Gamepad) modes to determine which controller type FH6 sends
vibration data to.

Usage:
    # Xbox 360 mode (default)
    python tools/fh6_rumble_debug.py

    # DualShock 4 mode
    python tools/fh6_rumble_debug.py --ds4

Then start FH6 and drive on dirt / hit a wall to trigger rumble.
All events are printed to console and saved to fh6_rumble_log.txt.
"""

import sys
import time
import argparse
import vgamepad as vg

LOG_FILE = "fh6_rumble_log.txt"


def on_rumble(client, target, large_motor, small_motor, led_number, user_data):
    """Log every rumble event with timestamp."""
    line = (f"[{time.strftime('%H:%M:%S')}] "
            f"large_motor={large_motor:3d}  "
            f"small_motor={small_motor:3d}  "
            f"led={led_number}  "
            f"target={target}")
    print(line)
    sys.stdout.flush()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(description="FH6 Rumble Debug Logger")
    parser.add_argument("--ds4", action="store_true", help="Use DualShock 4 virtual controller instead of Xbox 360")
    args = parser.parse_args()

    print("=" * 70)
    print(" FH6 Rumble Debug Logger")
    print("=" * 70)

    if args.ds4:
        print("[INFO] Creating virtual DualShock 4 controller...")
        gamepad = vg.VDS4Gamepad()
    else:
        print("[INFO] Creating virtual Xbox 360 controller...")
        gamepad = vg.VX360Gamepad()

    gamepad.register_notification(on_rumble)
    print("[OK ] Controller created. Notification callback registered.")
    print(f"[INFO] Logging to: {LOG_FILE}")
    print("[INFO] Start FH6 and drive.  Rumble events will be printed here.")
    print("       Press Ctrl+C to stop.\n")

    # Clear old log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"FH6 Rumble Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Controller type: {'DS4' if args.ds4 else 'Xbox 360'}\n")
        f.write("=" * 50 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")
        gamepad.unregister_notification()
        gamepad.reset()
        print(f"[INFO] Log saved to: {LOG_FILE}")
        print("Done.")


if __name__ == "__main__":
    main()
