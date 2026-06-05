"""
core/constants.py

Switch 2 Pro Controller (VID 0x057E / PID 0x2069) -> Xbox 360 Input Converter
Device constants and initialization sequences.
"""

# ---------------------------------------------------------------------------
# USB Device Identifiers
# ---------------------------------------------------------------------------
TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1  # Bulk OUT interface for initialization

# ---------------------------------------------------------------------------
# Initialization Commands (based on SDL's validated sequence for Switch 2 Pro)
# See: libsdl-org/SDL/src/joystick/hidapi/SDL_hidapi_switch2.c
#
# CRITICAL FIX:
#   The old sequence had 0x10 at index 12 (rumble enable) which is WRONG.
#   SDL uses 0x01 for rumble enablement. 0x10 was the original Switch Pro
#   subcommand prefix and does not apply to Switch 2 Pro over USB.
# ---------------------------------------------------------------------------
# SDL validated init sequence for Switch 2 Pro (SDL_hidapi_switch2.c)
# Order matters: "Start output" must be LAST.
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
#   [1]       = 0x50 | (seq & 0x0F)
#   [2-6]     = Left actuator rumble data (5 bytes)
#   [7-16]    = Padding (0x00)
#   [17]      = 0x50 | (seq & 0x0F)  (sequence copy)
#   [18-22]   = Right actuator rumble data (5 bytes, often copy of left)
#   [23-63]   = Padding (0x00)

# SDL default frequencies
RUMBLE_HF_FREQ = 0x0187  # ~600 Hz high-frequency default
RUMBLE_LF_FREQ = 0x0112  # ~260 Hz low-frequency default

# Safe amplitude maximum (SDL clamps to 29000 out of UINT16_MAX=65535)
RUMBLE_AMP_MAX = 29000
