"""
mapping/xbox360_mapper.py

Maps parsed Switch 2 Pro Controller inputs to a virtual Xbox 360 gamepad
using vgamepad (ViGEmBus).

Handles:
- Button mapping (positional / physical feel consistent)
- Stick axes (with polarity correction for joy.cpl compatibility)
- Trigger values (analog output)
"""

import vgamepad as vg

from core.input_parser import parse_buttons, parse_sticks, synthesize_triggers


class Xbox360Mapper:
    """Virtual Xbox 360 gamepad mapper and updater."""

    def __init__(self):
        self.gamepad = vg.VX360Gamepad()

    def update_from_payload(self, payload: list):
        """Parse a Switch input payload and update the virtual Xbox 360 state."""
        buttons = parse_buttons(payload)
        lx, ly, rx, ry = parse_sticks(payload)
        lt, rt = synthesize_triggers(buttons)

        # Face buttons (positional mapping)
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, buttons['B'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, buttons['A'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X, buttons['Y'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y, buttons['X'])

        # Shoulder buttons
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, buttons['L'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER, buttons['R'])

        # System buttons
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK, buttons['Minus'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START, buttons['Plus'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE, buttons['Home'])

        # Stick press buttons
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB, buttons['LStick'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB, buttons['RStick'])

        # D-Pad
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, buttons['Up'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, buttons['Down'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, buttons['Left'])
        self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT, buttons['Right'])

        # Left stick: Switch 2 Pro left stick Y raw has same polarity as Xbox 360
        self.gamepad.left_joystick(x_value=lx, y_value=ly)

        # Right stick: Switch 2 Pro right stick Y raw has opposite polarity
        self.gamepad.right_joystick(x_value=rx, y_value=-ry)

        # Triggers (synthesized from digital ZL/ZR)
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
