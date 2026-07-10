"""
core/constants.py

Switch 2 Pro Controller (VID 0x057E / PID 0x2069) -> Xbox 360 Input Converter
Device constants and initialization sequences.

Based on SDL's SDL_hidapi_switch2.c:
  https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_switch2.c
"""

# ---------------------------------------------------------------------------
# USB Device Identifiers
# ---------------------------------------------------------------------------
TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1  # Bulk OUT interface for initialization

# ---------------------------------------------------------------------------
# ReadFlashBlock Commands (sent BEFORE init_sequence in SDL)
#   Address: little-endian at bytes [12..15]
#   Response: 0x40 bytes at buffer[0x10..0x4F]
# ---------------------------------------------------------------------------
def _read_flash_cmd(address: int) -> bytes:
    """Build a ReadFlashBlock command for the given address."""
    cmd = bytearray(16)
    cmd[0] = 0x02
    cmd[1] = 0x91
    cmd[2] = 0x00
    cmd[3] = 0x01
    cmd[4] = 0x00
    cmd[5] = 0x08
    cmd[6] = 0x00
    cmd[7] = 0x00
    cmd[12] = address & 0xFF
    cmd[13] = (address >> 8) & 0xFF
    cmd[14] = (address >> 16) & 0xFF
    cmd[15] = (address >> 24) & 0xFF
    return bytes(cmd)

READ_FLASH_COMMANDS = [
    _read_flash_cmd(0x13000),   # Serial number
    _read_flash_cmd(0x13040),   # Gyro bias
    _read_flash_cmd(0x13080),   # Left stick calibration
    _read_flash_cmd(0x130C0),   # Right stick calibration
    _read_flash_cmd(0x13100),   # Accelerometer bias
]

# ---------------------------------------------------------------------------
# Initialization Commands (SDL's validated sequence for Switch 2 Pro)
#
# CRITICAL: SDL sends each command with length = cmd[5] + 8 bytes.
#   Example: 0x0A command has cmd[5]=0x14 (20) -> send 28 bytes.
#   All commands below are already sized to match SDL exactly.
#
# Order matters. "Start output" (0x03 0x0D) must be LAST.
# ---------------------------------------------------------------------------
INIT_COMMANDS = [
    bytes([0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0A, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0D, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
]

# SDL UpdateSlotLED command (sent after OpenJoystick, player_index=-1 -> pattern 0x06)
LED_COMMAND = bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

# ---------------------------------------------------------------------------
# Stick / Trigger Normalization Constants
# ---------------------------------------------------------------------------
STICK_MAX_RAW = 4095
STICK_CENTER = STICK_MAX_RAW / 2
STICK_SCALE = 32767

# Physical stick travel rarely reaches the theoretical raw 0/4095 endpoints
# (mechanical stop short of ADC saturation). Axes auto-calibrate their
# observed min/max at runtime; this margin lets readings within
# `margin` of the largest deflection seen so far saturate to full scale,
# so max tilt reliably reaches +/-32767 after a couple of full swings.
STICK_SATURATION_MARGIN = 0.92

# Switch 2 Pro reports ZL/ZR as digital buttons only.
# We synthesize analog trigger values from button states.
TRIGGER_DIGITAL_ON = 255
TRIGGER_DIGITAL_OFF = 0

# ---------------------------------------------------------------------------
# Rumble Constants (Switch 2 Pro specific, based on SDL implementation)
# See: libsdl-org/SDL/src/joystick/hidapi/SDL_hidapi_switch2.c
# ---------------------------------------------------------------------------
# Switch 2 Pro uses a completely different rumble protocol from original Switch Pro.
# - Report ID for rumble output: 0x02
# - Packet size: exactly 64 bytes
# - Sent via Interface 1 Bulk OUT (not HID Output Report).
# - Each actuator uses 5 bytes of HD Rumble 2 data (different bit packing).
# ---------------------------------------------------------------------------

# Report ID for Switch 2 Pro rumble output report
SWITCH2_RUMBLE_REPORT_ID = 0x02

# Neutral (no vibration) 5-byte actuator data
# EncodeHDRumble(0x187, 0, 0x112, 0) per SDL's EncodeHDRumble:
#   data[0] = 0x187 & 0xFF = 0x87
#   data[1] = ((0 >> 4) & 0xFC) | ((0x187 >> 8) & 0x03) = 0x01
#   data[2] = (0 >> 12) | ((0x112 << 4) & 0xFF) = 0x20
#   data[3] = (0 & 0xC0) | ((0x112 >> 4) & 0x3F) = 0x11
#   data[4] = 0 >> 8 = 0x00
RUMBLE_NEUTRAL_ACTUATOR = bytes([0x87, 0x01, 0x20, 0x11, 0x00])

# Packet layout (64 bytes total):
#   [0]       = Report ID (0x02)
#   [1]       = 0x50 | (seq & 0x0F)           ← sequence byte
#   [2-6]     = Left actuator rumble data (5 bytes)
#   [7-16]    = Padding (0x00)
#   [17]      = 0x50 | (seq & 0x0F)           ← seq copy  (SDL: 0x11 = 17 decimal)
#   [18-22]   = Right actuator (copy of left, 5 bytes)  (SDL: 0x12..0x16)
#   [23-63]   = Padding (0x00)
#
# SDL source: memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)
#   → report[17:23] = report[1:7]

# SDL default frequencies
RUMBLE_HF_FREQ = 0x0187  # ~600 Hz high-frequency default
RUMBLE_LF_FREQ = 0x0112  # ~260 Hz low-frequency default

# Safe amplitude maximum (SDL clamps to 29000 out of UINT16_MAX=65535)
RUMBLE_AMP_MAX = 29000
