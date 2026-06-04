"""
mapping/xbox360_mapper.py

Maps parsed Switch 2 Pro Controller inputs to a virtual Xbox 360 gamepad
using vgamepad (ViGEmBus).

Supports configurable button remapping, stick inversion, and trigger synthesis.
"""

import vgamepad as vg

from core.input_parser import parse_buttons, parse_sticks, synthesize_triggers
from mapping.xbox360_codes import XBOX_BUTTON_CODES


class Xbox360Mapper:
    """Virtual Xbox 360 gamepad mapper and updater."""

    def __init__(self, settings=None):
        self.gamepad = vg.VX360Gamepad()
        self.settings = settings

    def update_from_payload(self, payload: list):
        """Parse a Switch input payload and update the virtual Xbox 360 state."""
        buttons = parse_buttons(payload)
        lx, ly, rx, ry = parse_sticks(payload)
        lt, rt = synthesize_triggers(buttons)

        # Apply configurable stick inversion
        if self.settings:
            if self.settings.get("stick.left.invert_x", False):
                lx = -lx
            if self.settings.get("stick.left.invert_y", False):
                ly = -ly
            if self.settings.get("stick.right.invert_x", False):
                rx = -rx
            if self.settings.get("stick.right.invert_y", True):
                ry = -ry
        else:
            # Default: right stick Y inverted
            ry = -ry

        # Apply configurable button mapping
        mapping = self.settings.get("button_mapping") if self.settings else None
        if mapping is None:
            mapping = {
                "B": "B", "A": "A", "Y": "Y", "X": "X",
                "R": "RIGHT_SHOULDER",
                "ZR": None,          # ZR is analog trigger, handled via synthesize_triggers
                "Plus": "START", "RStick": "RIGHT_THUMB",
                "Down": "DPAD_DOWN", "Right": "DPAD_RIGHT",
                "Left": "DPAD_LEFT", "Up": "DPAD_UP",
                "L": "LEFT_SHOULDER",
                "ZL": None,          # ZL is analog trigger, handled via synthesize_triggers
                "Minus": "BACK", "LStick": "LEFT_THUMB",
                "Home": "GUIDE",
            }

        for switch_name, xbox_name in mapping.items():
            if xbox_name is None:
                continue
            pressed = buttons.get(switch_name, False)
            code = XBOX_BUTTON_CODES.get(xbox_name)
            if code:
                self._set_button(code, pressed)

        # Left stick
        self.gamepad.left_joystick(x_value=lx, y_value=ly)

        # Right stick
        self.gamepad.right_joystick(x_value=rx, y_value=ry)

        # Triggers (analog)
        self.gamepad.left_trigger(value=lt)
        self.gamepad.right_trigger(value=rt)

        # Push state to OS
        self.gamepad.update()

    def _set_button(self, button_code, pressed: bool):
        if pressed:
            self.gamepad.press_button(button_code)
        else:
            self.gamepad.release_button(button_code)

    def reset(self):
        """Reset all inputs to neutral."""
        self.gamepad.reset()

    def register_rumble_callback(self, callback):
        """Register a force-feedback callback on the virtual gamepad."""
        self.gamepad.register_notification(callback)
