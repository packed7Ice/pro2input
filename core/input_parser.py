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
    STICK_SCALE, STICK_SATURATION_MARGIN, STICK_DEFLECTION_FLOOR,
    TRIGGER_DIGITAL_ON, TRIGGER_DIGITAL_OFF,
)


def unpack_12bit_triplet(data: list) -> tuple[int, int]:
    """Unpack three bytes into two 12-bit values (stick X, Y)."""
    a = data[0] | ((data[1] & 0x0F) << 8)
    b = (data[1] >> 4) | (data[2] << 4)
    return a, b


class AxisCalibrator:
    """
    Auto-calibrates one stick axis at runtime.

    Physical stick travel rarely reaches the theoretical raw 0/4095
    endpoints, so a fixed ideal-range normalization leaves max tilt short
    of full scale. This tracks the largest deflection seen so far on each
    side of center and saturates readings within STICK_SATURATION_MARGIN
    of that deflection to +/-32767.

    The center is calibrated from the first raw sample received (assumed to
    be the physical rest position at connect time) rather than a fixed
    theoretical constant, since a given stick's true center can sit a bit
    off the theoretical midpoint. `_pos_extreme`/`_neg_extreme` start at
    STICK_DEFLECTION_FLOOR rather than ~0: seeding them near-zero meant a
    single sample with any small nonzero delta (idle ADC jitter, or the
    rest-position calibration itself landing slightly off on a later
    sample) was instantly treated as "the largest deflection ever seen",
    saturating that reading to full scale until a real, larger swing
    corrected it.
    """

    def __init__(self, margin: float = STICK_SATURATION_MARGIN):
        self.center: float | None = None
        self.margin = margin
        self._pos_extreme = STICK_DEFLECTION_FLOOR
        self._neg_extreme = STICK_DEFLECTION_FLOOR

    def normalize(self, raw_value: int) -> int:
        if self.center is None:
            self.center = float(raw_value)

        delta = raw_value - self.center
        if delta >= 0:
            self._pos_extreme = max(self._pos_extreme, delta)
            scale = self._pos_extreme * self.margin
        else:
            delta = -delta
            self._neg_extreme = max(self._neg_extreme, delta)
            scale = self._neg_extreme * self.margin

        norm = min(1.0, delta / scale)
        return int(norm * STICK_SCALE) if raw_value >= self.center else -int(norm * STICK_SCALE)


_lx_cal = AxisCalibrator()
_ly_cal = AxisCalibrator()
_rx_cal = AxisCalibrator()
_ry_cal = AxisCalibrator()


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

        # data[8] (payload[7]) - Extra buttons (back grip buttons)
        'GRButton': bool(payload[7] & 0x01),  # right back button
        'GLButton': bool(payload[7] & 0x02),  # left back button
    }


def parse_sticks(payload: list) -> tuple[int, int, int, int]:
    """Parse and normalize left/right stick axes (SDL data[11:17])."""
    lx_raw, ly_raw = unpack_12bit_triplet(payload[10:13])
    rx_raw, ry_raw = unpack_12bit_triplet(payload[13:16])

    lx = _lx_cal.normalize(lx_raw)
    ly = _ly_cal.normalize(ly_raw)
    rx = _rx_cal.normalize(rx_raw)
    ry = _ry_cal.normalize(ry_raw)

    return lx, ly, rx, ry


def synthesize_triggers(buttons: dict[str, bool]) -> tuple[int, int]:
    """
    Switch 2 Pro Controller reports ZL/ZR as digital buttons.
    Synthesize 0-255 analog trigger values from button states.
    """
    lt = TRIGGER_DIGITAL_ON if buttons['ZL'] else TRIGGER_DIGITAL_OFF
    rt = TRIGGER_DIGITAL_ON if buttons['ZR'] else TRIGGER_DIGITAL_OFF
    return lt, rt
