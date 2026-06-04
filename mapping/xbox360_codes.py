"""
mapping/xbox360_codes.py

Mapping between human-readable Xbox 360 button names and vgamepad constants.
"""

import vgamepad as vg

XBOX_BUTTON_CODES = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "LEFT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "RIGHT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    # NOTE: Xbox 360 triggers (LT/RT) are analog axes, not digital buttons.
    # They are handled via left_trigger()/right_trigger(), not button press.
    "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "GUIDE": vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "LEFT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "RIGHT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}

SWITCH_BUTTON_NAMES = [
    "B", "A", "Y", "X",
    "R", "ZR", "Plus", "RStick",
    "Down", "Right", "Left", "Up",
    "L", "ZL", "Minus", "LStick",
    "Home", "Capture", "CButton", "GRButton",
]
