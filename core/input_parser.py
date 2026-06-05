"""
core/input_parser.py

Parses raw HID input reports from Switch 2 Pro Controller into:
- Button states (digital)
- Stick axes (12-bit packed -> normalized signed 16-bit)
- Trigger values (synthesized from ZL/ZR digital buttons)

Payload offsets derived from SDL's HandleSwitchProState:
  libsdl-org/SDL/src/joystick/hidapi/SDL_hidapi_switch2.c

The raw HID report (64 bytes) read via pyusb Interrupt IN has Report ID at byte 0.
We skip it, so payload[i] corresponds to SDL's data[i+1].

SDL data offsets (from HandleSwitchProState):
  data[5] (payload[4]): Face buttons (Y/X/B/A), R, ZR
  data[6] (payload[5]): System buttons (Minus, Plus, RStick, LStick, Home, Share, C)
  data[7] (payload[6]): D-Pad (Down/Up/Right/Left), L, ZL
  data[8] (payload[7]): Extra buttons (GRButton)
  data[11:14] (payload[10:13]): Left stick (12-bit packed)
  data[14:17] (payload[13:16]): Right stick (12-bit packed)
"""

from core.constants import (
    STICK_MAX_RAW, STICK_CENTER, STICK_SCALE,
    TRIGGER_DIGITAL_ON, TRIGGER_DIGITAL_OFF,
)


def unpack_12bit_triplet(data: list) -> tuple[int, int]:
    """Unpack three bytes into two 12-bit values (stick X, Y)."""
    a = data[0] | ((data[1] & 0x0F) << 8)
    b = (data[1] >> 4) | (data[2] << 4)
    return a, b


def normalize_stick(value: int, max_raw: int = STICK_MAX_RAW) -> int:
    """Convert raw 12-bit value to signed 16-bit (-32768 to 32767)."""
    center = max_raw / 2
    return int((value - center) / center * STICK_SCALE)


def parse_buttons(payload: list) -> dict[str, bool]:
    """Parse button bytes from payload[4:8] (SDL data[5:9])."""
    return {
        # data[5] (payload[4]) - Face buttons
        # Switch 2 Pro bit layout (verified against SDL):
        #   bit0 = Y (top), bit1 = X (left), bit2 = B (bottom), bit3 = A (right)
        'Y': bool(payload[4] & 0x01),
        'X': bool(payload[4] & 0x02),
        'B': bool(payload[4] & 0x04),
        'A': bool(payload[4] & 0x08),
        'R': bool(payload[4] & 0x40),
        'ZR': bool(payload[4] & 0x80),

        # data[6] (payload[5]) - System buttons
        'Minus': bool(payload[5] & 0x01),
        'Plus': bool(payload[5] & 0x02),
        'RStick': bool(payload[5] & 0x04),
        'LStick': bool(payload[5] & 0x08),
        'Home': bool(payload[5] & 0x10),
        'Capture': bool(payload[5] & 0x20),
        'CButton': bool(payload[5] & 0x40),

        # data[7] (payload[6]) - D-Pad and left-side controls
        'Down': bool(payload[6] & 0x01),
        'Up': bool(payload[6] & 0x02),
        'Right': bool(payload[6] & 0x04),
        'Left': bool(payload[6] & 0x08),
        'L': bool(payload[6] & 0x40),
        'ZL': bool(payload[6] & 0x80),

        # data[8] (payload[7]) - Extra buttons
        'GRButton': bool(payload[7] & 0x01),
    }


def parse_sticks(payload: list) -> tuple[int, int, int, int]:
    """Parse and normalize left/right stick axes (SDL data[11:17])."""
    lx_raw, ly_raw = unpack_12bit_triplet(payload[10:13])
    rx_raw, ry_raw = unpack_12bit_triplet(payload[13:16])

    lx = normalize_stick(lx_raw)
    ly = normalize_stick(ly_raw)
    rx = normalize_stick(rx_raw)
    ry = normalize_stick(ry_raw)

    return lx, ly, rx, ry


def synthesize_triggers(buttons: dict[str, bool]) -> tuple[int, int]:
    """
    Switch 2 Pro Controller reports ZL/ZR as digital buttons.
    Synthesize 0-255 analog trigger values from button states.
    """
    lt = TRIGGER_DIGITAL_ON if buttons['ZL'] else TRIGGER_DIGITAL_OFF
    rt = TRIGGER_DIGITAL_ON if buttons['ZR'] else TRIGGER_DIGITAL_OFF
    return lt, rt
