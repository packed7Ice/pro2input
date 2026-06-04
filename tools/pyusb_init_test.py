import sys
import time
import usb.core
import usb.backend.libusb0

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  pyusb Init & Raw Data Sniffer
# ---------------------------------------------------------------------------
#  Uses pyusb with libusb0 backend (libusb0.dll) for direct USB I/O.
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  pyusb Init & Raw Data Sniffer")
    print(" VID: 0x057E  |  PID: 0x2069")
    print("=" * 80)

    # Find the device
    print("\n[INFO] Searching for device...")
    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("\n[FATAL] Device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Did you replace the driver with WinUSB/libusbK via Zadig?")
        print("  3. Try unplugging and reconnecting the USB cable.")
        sys.exit(1)

    print(f"[OK ] Device found: {dev}")
    print(f"       Bus: {dev.bus}, Address: {dev.address}")

    # Set configuration
    print("\n[INFO] Setting configuration...")
    dev.set_configuration()

    # Get active configuration
    cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=1)
    if intf is None:
        print("[WARN] Interface 1 not found, trying Interface 0...")
        intf = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    
    if intf is None:
        print("[FATAL] No suitable interface found.")
        sys.exit(1)

    print(f"[OK ] Using interface: {intf.bInterfaceNumber}")

    # Find endpoints
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )
    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if ep_out is None or ep_in is None:
        print("[FATAL] Could not find endpoints.")
        sys.exit(1)

    print(f"[OK ] OUT endpoint: 0x{ep_out.bEndpointAddress:02X}")
    print(f"[OK ] IN endpoint: 0x{ep_in.bEndpointAddress:02X}")

    # Claim interface
    print("\n[INFO] Claiming interface...")
    usb.util.claim_interface(dev, intf.bInterfaceNumber)
    print(f"[OK ] Interface {intf.bInterfaceNumber} claimed.")

    # Try initialization
    init_sequences = [
        ("64-byte zeros", bytes([0x00] * 64)),
        ("Handshake 0x80 0x01", bytes([0x80, 0x01] + [0x00] * 62)),
        ("Handshake 0x80 0x02", bytes([0x80, 0x02] + [0x00] * 62)),
        ("Report Mode 0x3F", bytes([0x01, 0x00] + [0x00] * 8 + [0x03, 0x3F] + [0x00] * 52)),
        ("Report Mode 0x30", bytes([0x01, 0x00] + [0x00] * 8 + [0x03, 0x30] + [0x00] * 52)),
    ]

    initialized = False
    for name, data in init_sequences:
        print(f"\n[INIT] Trying: {name}")
        try:
            dev.write(ep_out.bEndpointAddress, data)
            print(f"  [OK ] Write succeeded ({len(data)} bytes)")
            time.sleep(0.5)
            
            # Try reading multiple times
            for i in range(5):
                try:
                    reply = dev.read(ep_in.bEndpointAddress, 64, timeout=300)
                    if reply:
                        print(f"  [OK ] Controller responded ({len(reply)} bytes)!")
                        initialized = True
                        break
                except usb.core.USBError as e:
                    if e.errno == 110:  # Timeout
                        print("  [INFO] Read timeout, retrying...")
                        time.sleep(0.2)
                    else:
                        print(f"  [WARN] Read error: {e}")
                        break
            if initialized:
                break
        except usb.core.USBError as e:
            print(f"  [WARN] Write failed: {e}")

    if not initialized:
        print("\n[INIT] No immediate response. Trying to read anyway...")
        print("       The controller might already be sending data.")
        
    print("\n" + "=" * 80)
    print("[READ] Entering main read loop.  Press Ctrl+C to stop.")
    print("=" * 80)

    try:
        while True:
            try:
                data = dev.read(ep_in.bEndpointAddress, 64, timeout=5000)
                if data:
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    print(f"RECV [{len(data):2d}]: {hex_str}")
            except usb.core.USBError as e:
                if e.errno == 110:  # Timeout
                    print(".", end="", flush=True)
                else:
                    print(f"\n[ERROR] {e}")
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    print("\n[INFO] Releasing interface...")
    usb.util.release_interface(dev, intf.bInterfaceNumber)
    print("Done.")


if __name__ == "__main__":
    main()
