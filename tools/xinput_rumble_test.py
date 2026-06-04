"""
tools/xinput_rumble_test.py

Sends XInput force-feedback (rumble) commands directly to any connected
virtual or physical Xbox 360 controller.

Usage:
    python tools/xinput_rumble_test.py

This will cycle through Player 0-3, sending left/right motor vibrations
for 0.5 seconds each.  Use this to verify that the Switch 2 Pro Controller
receives rumble data when it is mapped through main.py.
"""

import ctypes
import time
from ctypes import wintypes


# ---------------------------------------------------------------------------
# XInput Vibration Structures
# ---------------------------------------------------------------------------
class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", wintypes.WORD),   # Low-frequency motor  (0-65535)
        ("wRightMotorSpeed", wintypes.WORD),  # High-frequency motor (0-65535)
    ]


def load_xinput() -> ctypes.CDLL:
    """Load the XInput DLL (1.4 preferred, fallback to 1.3)."""
    try:
        return ctypes.windll.xinput1_4
    except OSError:
        return ctypes.windll.xinput1_3


def set_rumble(xinput: ctypes.CDLL, player_id: int, left: float, right: float) -> int:
    """
    Set vibration for a given player index.
    left/right are 0.0-1.0 intensity values.
    Returns 0 on success, ERROR_DEVICE_NOT_CONNECTED (1167) if no controller.
    """
    xv = XINPUT_VIBRATION()
    xv.wLeftMotorSpeed = int(left * 65535)
    xv.wRightMotorSpeed = int(right * 65535)
    return xinput.XInputSetState(player_id, ctypes.byref(xv))


def main():
    print("=" * 60)
    print(" XInput Rumble Test")
    print("=" * 60)
    print("\n[INFO] Searching for XInput controllers (Player 0-3)...")
    print("       Make sure main.py is running so the virtual controller exists.")
    print("       Press Ctrl+C to stop early.\n")

    xinput = load_xinput()
    any_found = False

    for player in range(4):
        result = set_rumble(xinput, player, 0.0, 0.0)
        if result != 0:
            # ERROR_DEVICE_NOT_CONNECTED or similar
            print(f"  Player {player}: No controller")
            continue

        any_found = True
        print(f"  Player {player}: Controller found!")

        # Left motor (large / low frequency) -> 1 second
        print(f"    -> Left motor (low freq)  ON")
        set_rumble(xinput, player, 1.0, 0.0)
        time.sleep(1.0)

        # Right motor (small / high frequency) -> 1 second
        print(f"    -> Right motor (high freq) ON")
        set_rumble(xinput, player, 0.0, 1.0)
        time.sleep(1.0)

        # Both motors -> 1 second
        print(f"    -> Both motors ON")
        set_rumble(xinput, player, 1.0, 1.0)
        time.sleep(1.0)

        # Stop
        print(f"    -> OFF\n")
        set_rumble(xinput, player, 0.0, 0.0)

    if not any_found:
        print("\n[WARN] No XInput controllers found.")
        print("       Is main.py running? Did ViGEmBus install correctly?")
    else:
        print("[OK ] Rumble test complete.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Cancelled by user.")
        # Make sure all motors are off
        try:
            xinput = load_xinput()
            for p in range(4):
                set_rumble(xinput, p, 0.0, 0.0)
        except Exception:
            pass
