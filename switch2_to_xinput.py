import sys
import time
import math
import usb.core
import usb.util
import vgamepad as vg

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069) -> Xbox 360 Input
#  Main Converter Script
# ---------------------------------------------------------------------------
#  Requires:
#    pip install pyusb vgamepad
#    libusb-1.0.dll in C:\Windows\System32
#    ViGEmBus driver installed
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1

# Initialization Commands (from enable_hid.py)
INIT_COMMANDS = [
    bytes([0x03, 0x91, 0x00, 0x0D, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x16, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x15, 0x91, 0x00, 0x01, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x02, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x15, 0x91, 0x00, 0x02, 0x00, 0x11, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x15, 0x91, 0x00, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x11, 0x91, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0A, 0x00, 0x04, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00]),
    bytes([0x10, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x03, 0x00, 0x00]),
    bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
]


def init_controller(dev):
    """Initialize the controller via Interface 1 (Bulk OUT)."""
    cfg = dev.get_active_configuration()
    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    
    ep_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break
    
    if ep_out is None:
        raise RuntimeError("Bulk OUT endpoint not found on Interface 1")
    
    try:
        usb.util.claim_interface(dev, USB_INTERFACE_NUMBER)
    except usb.core.USBError:
        pass
    
    for cmd in INIT_COMMANDS:
        try:
            dev.write(ep_out, cmd)
        except usb.core.USBError:
            pass
        time.sleep(0.05)
    
    try:
        usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
    except Exception:
        pass
    
    return cfg


def unpack_12bit_triplet(data):
    """Unpack three bytes into two 12-bit values (stick X, Y)."""
    a = data[0] | ((data[1] & 0x0F) << 8)
    b = (data[1] >> 4) | (data[2] << 4)
    return a, b


def normalize_stick(value, max_raw=4095):
    """Convert raw 12-bit value to signed 16-bit (-32768 to 32767)."""
    center = max_raw / 2
    return int((value - center) / center * 32767)


def normalize_trigger(value, min_in=0, max_in=255):
    """Normalize trigger value to 0-255 range."""
    if value < min_in:
        value = min_in
    if value > max_in:
        value = max_in
    return int((value - min_in) / (max_in - min_in) * 255)


def parse_buttons(payload):
    """Parse button bytes from payload[0x2:0x5] based on enable_hid.py reference."""
    b = payload[2:5]
    return {
        # Byte 0 (buttons[0])
        'B': bool(b[0] & 0x01),        # bit 0: B (bottom button)
        'A': bool(b[0] & 0x02),        # bit 1: A (right button)
        'Y': bool(b[0] & 0x04),        # bit 2: Y (left button)
        'X': bool(b[0] & 0x08),        # bit 3: X (top button)
        'SR_R': bool(b[0] & 0x10),     # bit 4: SR (right joycon)
        'SL_R': bool(b[0] & 0x20),     # bit 5: SL (right joycon)
        'R': bool(b[0] & 0x40),        # bit 6: R (right shoulder)
        'ZR': bool(b[0] & 0x80),       # bit 7: ZR (right trigger)
        
        # Byte 1 (buttons[1])
        'Minus': bool(b[1] & 0x01),    # bit 0: Minus
        'Plus': bool(b[1] & 0x02),     # bit 1: Plus
        'RStick': bool(b[1] & 0x04),   # bit 2: RStick press
        'LStick': bool(b[1] & 0x08),   # bit 3: LStick press
        'Home': bool(b[1] & 0x10),     # bit 4: Home
        'Capture': bool(b[1] & 0x20),   # bit 5: Capture (Screenshot)
        'CButton': bool(b[1] & 0x40),  # bit 6: C Button (Game Chat)
        'GRButton': bool(b[1] & 0x80),  # bit 7: GR (Back button)
        
        # Byte 2 (buttons[2])
        'Down': bool(b[2] & 0x01),     # bit 0: D-Pad Down
        'Right': bool(b[2] & 0x02),   # bit 1: D-Pad Right
        'Left': bool(b[2] & 0x04),    # bit 2: D-Pad Left
        'Up': bool(b[2] & 0x08),       # bit 3: D-Pad Up
        'SR_L': bool(b[2] & 0x10),     # bit 4: SR (left joycon)
        'SL_L': bool(b[2] & 0x20),     # bit 5: SL (left joycon)
        'L': bool(b[2] & 0x40),        # bit 6: L (left shoulder)
        'ZL': bool(b[2] & 0x80),       # bit 7: ZL (left trigger)
    }


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller -> Xbox 360 Input Converter")
    print(" For Forza Horizon 6 / PC")
    print("=" * 80)
    
    # Initialize virtual gamepad
    print("\n[INFO] Creating virtual Xbox 360 controller...")
    gamepad = vg.VX360Gamepad()
    print("[OK ] Virtual Xbox 360 controller created.")
    
    # Find physical controller
    print("\n[INFO] Searching for Switch 2 Pro Controller...")
    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Is the controller powered on?")
        print("  3. Are drivers (libusbK) correctly installed via Zadig?")
        sys.exit(1)
    
    print(f"[OK ] Device found: {dev}")
    dev.set_configuration()
    
    # Initialize controller
    print("\n[INFO] Initializing controller...")
    cfg = init_controller(dev)
    print("[OK ] Controller initialized.")
    
    # Get Interface 0 endpoints
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_in = usb.util.find_descriptor(
        intf0,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )
    
    if ep0_in is None:
        print("[FATAL] Interrupt IN endpoint not found on Interface 0.")
        sys.exit(1)
    
    try:
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError:
        pass
    
    print(f"\n[OK ] Interface 0 IN endpoint: 0x{ep0_in.bEndpointAddress:02X}")
    print("[INFO] Starting input loop. Press Ctrl+C to stop.")
    print("[INFO] Open Forza Horizon 6 and enjoy!\n")
    
    try:
        while True:
            try:
                data = dev.read(ep0_in.bEndpointAddress, 64, timeout=1000)
                if data:
                    payload = list(data)[1:]  # Skip Report ID
                    
                    # Parse buttons
                    buttons = parse_buttons(payload)
                    
                    # Parse sticks (12-bit packed)
                    lx_raw, ly_raw = unpack_12bit_triplet(payload[5:8])
                    rx_raw, ry_raw = unpack_12bit_triplet(payload[8:11])
                    
                    # Normalize
                    lx = normalize_stick(lx_raw)
                    ly = normalize_stick(ly_raw)
                    rx = normalize_stick(rx_raw)
                    ry = normalize_stick(ry_raw)
                    
                    # Triggers
                    lt_raw = payload[0x0C]
                    rt_raw = payload[0x0D]
                    lt = normalize_trigger(lt_raw)
                    rt = normalize_trigger(rt_raw)
                    
                    # Update virtual gamepad
                    # Positional button mapping (physical feel consistent)
                    # Switch B (bottom) → Xbox A
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A) if buttons['B'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    # Switch A (right) → Xbox B
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B) if buttons['A'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    # Switch Y (left) → Xbox X
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X) if buttons['Y'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X)
                    # Switch X (top) → Xbox Y
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y) if buttons['X'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
                    
                    # Shoulder buttons
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER) if buttons['L'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER) if buttons['R'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
                    
                    # System buttons
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK) if buttons['Minus'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK)
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START) if buttons['Plus'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START)
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE) if buttons['Home'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE)
                    
                    # Stick press buttons
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB) if buttons['LStick'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB)
                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB) if buttons['RStick'] else gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
                    
                    # Extra buttons (Switch 2 specific - mapped to unused Xbox buttons)
                    # Capture (Screenshot) → mapped to unused button for now
                    # gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_??) if buttons['Capture'] else ...
                    
                    # D-Pad (using POV/Hat Switch)
                    if buttons['Up'] and buttons['Right']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_UP_RIGHT
                    elif buttons['Up'] and buttons['Left']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_UP_LEFT
                    elif buttons['Down'] and buttons['Right']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_DOWN_RIGHT
                    elif buttons['Down'] and buttons['Left']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_DOWN_LEFT
                    elif buttons['Up']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_UP
                    elif buttons['Down']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_DOWN
                    elif buttons['Left']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_LEFT
                    elif buttons['Right']:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_RIGHT
                    else:
                        gamepad.dpad = vg.XUSB_DPAD.XUSB_GAMEPAD_DPAD_NONE
                    
                    # Left stick (Y-axis inverted for Xbox)
                    gamepad.left_joystick(x_value=lx, y_value=-ly)
                    
                    # Right stick (Y-axis inverted for Xbox)
                    gamepad.right_joystick(x_value=rx, y_value=-ry)
                    
                    # Triggers (analog)
                    gamepad.left_trigger(value=lt)
                    gamepad.right_trigger(value=rt)
                    
                    # Update
                    gamepad.update()
                    
            except usb.core.USBError as e:
                if e.errno == 110 or e.errno == 10060:
                    pass  # Timeout, continue
                else:
                    print(f"\n[ERROR] {e}")
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    
    # Cleanup
    print("\n[INFO] Cleaning up...")
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass
    
    gamepad.reset()
    print("[OK ] Virtual controller reset.")
    print("Done.")


if __name__ == "__main__":
    main()
