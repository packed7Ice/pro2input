import sys
import time
import usb.core
import usb.backend.libusb0

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Extended Init Test with longer timeouts
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Extended Init Test")
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

    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )
    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if ep_out is None or ep_in is None:
        print("[FATAL] Endpoints not found.")
        sys.exit(1)

    print(f"[OK ] OUT: 0x{ep_out.bEndpointAddress:02X}, IN: 0x{ep_in.bEndpointAddress:02X}")
    print("[INFO] Claiming interface...")
    usb.util.claim_interface(dev, intf.bInterfaceNumber)
    print("[OK ] Interface claimed.")

    # Try different init sequences with longer timeouts
    init_sequences = [
        ("64-byte zeros", bytes([0x00] * 64)),
        ("Handshake 0x80 0x01", bytes([0x80, 0x01] + [0x00] * 62)),
        ("Handshake 0x80 0x02", bytes([0x80, 0x02] + [0x00] * 62)),
        ("Handshake 0x80 0x03", bytes([0x80, 0x03] + [0x00] * 62)),
        ("Report Mode 0x3F", bytes([0x01, 0x00] + [0x00] * 8 + [0x03, 0x3F] + [0x00] * 52)),
        ("Report Mode 0x30", bytes([0x01, 0x00] + [0x00] * 8 + [0x03, 0x30] + [0x00] * 52)),
        ("Request Dev Info (0x02)", bytes([0x01, 0x00] + [0x00] * 8 + [0x02, 0x00] + [0x00] * 52)),
        ("Set HCI state (0x06)", bytes([0x01, 0x00] + [0x00] * 8 + [0x06, 0x01] + [0x00] * 52)),
    ]

    for name, data in init_sequences:
        print(f"\n[INIT] Trying: {name}")
        try:
            dev.write(ep_out.bEndpointAddress, data)
            print(f"  [OK ] Write succeeded ({len(data)} bytes)")
            
            # Try reading with increasing timeouts
            for timeout_ms in [1000, 2000, 5000, 10000]:
                try:
                    reply = dev.read(ep_in.bEndpointAddress, 64, timeout=timeout_ms)
                    if reply:
                        print(f"  [OK ] Controller responded ({len(reply)} bytes)!")
                        print(f"  [DATA] {reply.tobytes().hex()}")
                        
                        print("\n" + "=" * 80)
                        print("[READ] Entering main read loop. Press Ctrl+C to stop.")
                        print("=" * 80)
                        
                        try:
                            while True:
                                try:
                                    data = dev.read(ep_in.bEndpointAddress, 64, timeout=5000)
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
                        return
                except usb.core.USBError as e:
                    if e.errno == 110:
                        print(f"  [INFO] Timeout ({timeout_ms}ms), retrying...")
                    else:
                        print(f"  [WARN] Read error: {e}")
                        break
        except usb.core.USBError as e:
            print(f"  [WARN] Write failed: {e}")

    print("\n[FATAL] Could not initialize device.")
    print("\nPossible reasons:")
    print("  1. Controller is not powered on or in sleep mode.")
    print("  2. Controller needs a different initialization sequence.")
    print("  3. Another application is holding the device.")
    print("\nTry pressing the Home button or A button to wake up the controller.")
    
    print("\n[INFO] Releasing interface...")
    usb.util.release_interface(dev, intf.bInterfaceNumber)
    print("Done.")


if __name__ == "__main__":
    main()
