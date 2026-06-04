"""
core/input_parser.py

Parses raw HID input reports from Switch 2 Pro Controller into:
- Button states (digital)
- Stick axes (12-bit packed -> normalized signed 16-bit)
- Trigger values (synthesized from ZL/ZR digital buttons)
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
    """Parse button bytes from payload[0x2:0x5]."""
    b = payload[2:5]
    return {
        # Byte 0 (payload[2]) - Face buttons and right-side controls
        'B': bool(b[0] & 0x01),
        'A': bool(b[0] & 0x02),
        'Y': bool(b[0] & 0x04),
        'X': bool(b[0] & 0x08),
        'R': bool(b[0] & 0x10),
        'ZR': bool(b[0] & 0x20),
        'Plus': bool(b[0] & 0x40),
        'RStick': bool(b[0] & 0x80),

        # Byte 1 (payload[3]) - D-Pad and left-side controls
        'Down': bool(b[1] & 0x01),
        'Right': bool(b[1] & 0x02),
        'Left': bool(b[1] & 0x04),
        'Up': bool(b[1] & 0x08),
        'L': bool(b[1] & 0x10),
        'ZL': bool(b[1] & 0x20),
        'Minus': bool(b[1] & 0x40),
        'LStick': bool(b[1] & 0x80),

        # Byte 2 (payload[4]) - System buttons
        'Home': bool(b[2] & 0x01),
        'Capture': bool(b[2] & 0x02),
        'CButton': bool(b[2] & 0x04),
        'GRButton': bool(b[2] & 0x08),
    }


def parse_sticks(payload: list) -> tuple[int, int, int, int]:
    """Parse and normalize left/right stick axes."""
    lx_raw, ly_raw = unpack_12bit_triplet(payload[5:8])
    rx_raw, ry_raw = unpack_12bit_triplet(payload[8:11])

    lx = normalize_stick(lx_raw)
    ly = normalize_stick(ly_raw)
    rx = normalize_stick(rx_raw)
    ry = normalize_stick(ry_raw)

    return lx, ly, rx, ry


def synthesize_triggers(buttons: dict[str, bool]) -> tuple[int, int]:
    """
    Switch 2 Pro Controller reports ZL/ZR as digital buttons only.
    Synthesize 0-255 analog trigger values from button states.
    """
    lt = TRIGGER_DIGITAL_ON if buttons['ZL'] else TRIGGER_DIGITAL_OFF
    rt = TRIGGER_DIGITAL_ON if buttons['ZR'] else TRIGGER_DIGITAL_OFF
    return lt, rt
