import sys
import time
import usb.core
import usb.util

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  NSW2 Init & Read Test  --  Based on enable_hid.py
# ---------------------------------------------------------------------------
#  Uses pyusb + libusb-1.0 to send initialization commands via Interface 1
#  (Bulk OUT), then reads HID reports from Interface 0 (Interrupt IN).
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


def find_device():
    """Find the Switch 2 Pro Controller."""
    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    return dev


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  NSW2 Init & Read Test")
    print(" Based on ikz87/NSW2-controller-enabler")
    print("=" * 80)

    # Step 1: Find device
    print("\n[INFO] Searching for device...")
    dev = find_device()
    if dev is None:
        print("\n[FATAL] Device not found.")
        sys.exit(1)
    print(f"[OK ] Device found: {dev}")

    # Step 2: Set configuration
    print("[INFO] Setting configuration...")
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    print(f"[OK ] Configuration set.")

    # Step 3: Find Interface 1 endpoints
    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    if intf1 is None:
        print("[FATAL] Interface 1 not found.")
        sys.exit(1)

    ep_out = None
    ep_in = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
        elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
            ep_in = ep.bEndpointAddress

    if ep_out is None:
        print("[FATAL] Bulk OUT endpoint not found on Interface 1.")
        sys.exit(1)

    ep_in_str = f"0x{ep_in:02X}" if ep_in else "N/A"
    print(f"[OK ] Interface 1: OUT=0x{ep_out:02X}, IN={ep_in_str}")

    # Step 4: Claim Interface 1
    print("[INFO] Claiming Interface 1...")
    try:
        usb.util.claim_interface(dev, USB_INTERFACE_NUMBER)
        print("[OK ] Interface 1 claimed.")
    except usb.core.USBError as e:
        print(f"[WARN] Could not claim Interface 1: {e}")
        print("       Trying to continue anyway...")

    # Step 5: Send initialization sequence
    print("\n[INFO] Sending initialization sequence...")
    for i, cmd in enumerate(INIT_COMMANDS):
        name = f"Command {i+1}/{len(INIT_COMMANDS)} (0x{cmd[0]:02X})"
        print(f"  [INIT] {name}: {cmd.hex()}")
        try:
            dev.write(ep_out, cmd)
            print(f"  [OK ] Write succeeded ({len(cmd)} bytes)")
            if ep_in:
                try:
                    time.sleep(0.01)
                    reply = dev.read(ep_in, 64, timeout=100)
                    if reply:
                        print(f"  [OK ] Response: {reply.tobytes().hex()}")
                except usb.core.USBError:
                    pass  # No response expected for most commands
        except usb.core.USBError as e:
            print(f"  [WARN] Write failed: {e}")
        time.sleep(0.05)
    print("[OK ] Initialization sequence complete!")

    # Step 6: Release Interface 1 and claim Interface 0
    print("\n[INFO] Releasing Interface 1...")
    try:
        usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
        print("[OK ] Interface 1 released.")
    except Exception as e:
        print(f"[WARN] {e}")

    # Step 7: Try to read from Interface 0
    print("\n[INFO] Switching to Interface 0 (HID)...")
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    if intf0 is None:
        print("[FATAL] Interface 0 not found.")
        sys.exit(1)

    ep0_in = usb.util.find_descriptor(
        intf0,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if ep0_in is None:
        print("[FATAL] Interrupt IN endpoint not found on Interface 0.")
        sys.exit(1)

    print(f"[OK ] Interface 0: IN=0x{ep0_in.bEndpointAddress:02X}")

    print("[INFO] Claiming Interface 0...")
    try:
        usb.util.claim_interface(dev, 0)
        print("[OK ] Interface 0 claimed.")
    except usb.core.USBError as e:
        print(f"[WARN] Could not claim Interface 0: {e}")
        print("       The interface may be occupied by Windows HID driver.")
        print("       If so, please try running after changing Interface 0")
        print("       back to HidUsb in Zadig.")
        sys.exit(1)

    # Step 8: Read loop
    print("\n" + "=" * 80)
    print("[READ] Entering read loop. Press buttons on the controller.")
    print("       Press Ctrl+C to stop.")
    print("=" * 80)

    try:
        while True:
            try:
                data = dev.read(ep0_in.bEndpointAddress, 64, timeout=1000)
                if data:
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    print(f"RECV [{len(data):2d}]: {hex_str}")
            except usb.core.USBError as e:
                if e.errno == 110 or e.errno == 10060:
                    print(".", end="", flush=True)
                else:
                    print(f"\n[ERROR] {e}")
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    # Cleanup
    print("\n[INFO] Releasing Interface 0...")
    try:
        usb.util.release_interface(dev, 0)
        print("[OK ] Interface 0 released.")
    except Exception as e:
        print(f"[WARN] {e}")

    print("Done.")


if __name__ == "__main__":
    main()
