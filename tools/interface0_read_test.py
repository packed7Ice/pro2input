import sys
import time
import usb.core
import usb.backend.libusb0

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Interface 0 Read Test (HID Interrupt Endpoints)
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Interface 0 Interrupt Read Test")
    print("=" * 80)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("\n[FATAL] Device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Did you replace BOTH Interface 0 and Interface 1 with libusbK?")
        sys.exit(1)

    print(f"[OK ] Device found: {dev}")
    print(f"       Bus: {dev.bus}, Address: {dev.address}")

    # Set configuration
    print("\n[INFO] Setting configuration...")
    dev.set_configuration()

    # Get active configuration
    cfg = dev.get_active_configuration()
    
    # Interface 0 is HID with Interrupt endpoints
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    if intf is None:
        print("[FATAL] Interface 0 not found.")
        sys.exit(1)

    print(f"[OK ] Interface 0 found (bInterfaceClass={intf.bInterfaceClass})")

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
        print("[FATAL] Could not find endpoints on Interface 0.")
        sys.exit(1)

    print(f"[OK ] OUT endpoint: 0x{ep_out.bEndpointAddress:02X}")
    print(f"[OK ] IN endpoint: 0x{ep_in.bEndpointAddress:02X}")
    print(f"[OK ] Packet size: {ep_in.wMaxPacketSize} bytes")
    print(f"[OK ] Interval: {ep_in.bInterval} ms")

    # Claim interface
    print("\n[INFO] Claiming Interface 0...")
    usb.util.claim_interface(dev, intf.bInterfaceNumber)
    print(f"[OK ] Interface {intf.bInterfaceNumber} claimed.")

    # Try to read without init (HID devices usually start sending data immediately)
    print("\n[INFO] Reading from Interrupt IN endpoint...")
    print("[INFO] Press buttons on the controller to generate data.")
    print("[INFO] Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                # Read with timeout
                data = dev.read(ep_in.bEndpointAddress, ep_in.wMaxPacketSize, timeout=1000)
                if data:
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    print(f"RECV [{len(data):2d}]: {hex_str}")
            except usb.core.USBError as e:
                if e.errno == 110 or e.errno == 10060:  # Timeout
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
