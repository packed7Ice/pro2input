import sys
import time
import usb.core
import usb.backend.libusb0

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Simple Read Test  --  No init, just read
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Simple Read Test")
    print("=" * 80)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("\n[FATAL] Device not found.")
        sys.exit(1)

    print(f"[OK ] Device found: {dev}")
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=1)
    if intf is None:
        intf = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    
    if intf is None:
        print("[FATAL] No interface found.")
        sys.exit(1)

    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if ep_in is None:
        print("[FATAL] No IN endpoint found.")
        sys.exit(1)

    print(f"[OK ] IN endpoint: 0x{ep_in.bEndpointAddress:02X}")
    print("[INFO] Claiming interface...")
    usb.util.claim_interface(dev, intf.bInterfaceNumber)
    print("[OK ] Interface claimed.")

    print("\n[INFO] Reading without any init...")
    print("[INFO] Press buttons on the controller to see data.")
    print("[INFO] Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                # Try reading with different sizes
                data = dev.read(ep_in.bEndpointAddress, 64, timeout=1000)
                if data:
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    print(f"RECV [{len(data):2d}]: {hex_str}")
            except usb.core.USBError as e:
                if e.errno == 110:
                    print(".", end="", flush=True)
                else:
                    print(f"\n[ERROR] {e}")
                    break
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    print("\n[INFO] Releasing interface...")
    usb.util.release_interface(dev, intf.bInterfaceNumber)
    print("Done.")


if __name__ == "__main__":
    main()
