import sys
import time
import usb.core
import usb.util

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Button Test Script - Shows which button is pressed
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1

# Initialization Commands
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
    cfg = dev.get_active_configuration()
    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    ep_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break
    if ep_out is None:
        raise RuntimeError("Bulk OUT endpoint not found")
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

def parse_buttons(payload):
    b = payload[2:5]
    return {
        'B': bool(b[0] & 0x01),
        'A': bool(b[0] & 0x02),
        'Y': bool(b[0] & 0x04),
        'X': bool(b[0] & 0x08),
        'R': bool(b[0] & 0x10),
        'ZR': bool(b[0] & 0x20),
        'Plus': bool(b[0] & 0x40),
        'RStick': bool(b[0] & 0x80),
        'Down': bool(b[1] & 0x01),
        'Right': bool(b[1] & 0x02),
        'Left': bool(b[1] & 0x04),
        'Up': bool(b[1] & 0x08),
        'L': bool(b[1] & 0x10),
        'ZL': bool(b[1] & 0x20),
        'Minus': bool(b[1] & 0x40),
        'LStick': bool(b[1] & 0x80),
        'Home': bool(b[2] & 0x01),
        'Capture': bool(b[2] & 0x02),
        'CButton': bool(b[2] & 0x04),
        'GRButton': bool(b[2] & 0x08),
    }

def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Button Test")
    print("=" * 80)
    print("\n[INFO] Press buttons on the controller to see their names.")
    print("       Press Ctrl+C to stop.\n")
    
    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)
    
    dev.set_configuration()
    cfg = init_controller(dev)
    
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_in = usb.util.find_descriptor(
        intf0,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )
    
    if ep0_in is None:
        print("[FATAL] Interrupt IN endpoint not found.")
        sys.exit(1)
    
    try:
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError:
        pass
    
    last_buttons = {}
    try:
        while True:
            try:
                data = dev.read(ep0_in.bEndpointAddress, 64, timeout=100)
                if data:
                    payload = list(data)[1:]
                    buttons = parse_buttons(payload)
                    
                    # Show pressed buttons
                    pressed = [name for name, value in buttons.items() if value]
                    if pressed:
                        print(f"Pressed: {', '.join(pressed)}")
                    
                    # Show button state changes
                    for name, value in buttons.items():
                        if name not in last_buttons:
                            last_buttons[name] = False
                        if value != last_buttons[name]:
                            if value:
                                print(f"  -> {name} PRESSED")
                            else:
                                print(f"  -> {name} RELEASED")
                            last_buttons[name] = value
            except usb.core.USBError:
                pass
    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")
    
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass
    print("Done.")

if __name__ == "__main__":
    main()
