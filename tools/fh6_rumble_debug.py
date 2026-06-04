"""
tools/fh6_rumble_debug.py

Captures and logs all force-feedback (rumble) events received by the
virtual Xbox 360 controller.  Use this to determine whether FH6 is
sending vibration data at all, and if so, what values.

Usage:
    Terminal 1: python main.py
    Terminal 2: python tools/fh6_rumble_debug.py
    Then start FH6 and drive on dirt / hit a wall to trigger rumble.
"""

import sys
import time
import vgamepad as vg


def on_rumble(client, target, large_motor, small_motor, led_number, user_data):
    """Log every rumble event with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] "
          f"large_motor={large_motor:3d}  "
          f"small_motor={small_motor:3d}  "
          f"led={led_number}  "
          f"target={target}")
    sys.stdout.flush()


def main():
    print("=" * 70)
    print(" FH6 Rumble Debug Logger")
    print("=" * 70)
    print("\n[INFO] Creating virtual Xbox 360 controller...")
    gamepad = vg.VX360Gamepad()
    gamepad.register_notification(on_rumble)
    print("[OK ] Controller created. Notification callback registered.")
    print("[INFO] Start FH6 and drive.  Rumble events will be printed here.")
    print("       Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")
        gamepad.unregister_notification()
        gamepad.reset()
        print("Done.")


if __name__ == "__main__":
    main()
