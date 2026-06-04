"""
tools/rumble_hid_control_test.py

Tries sending rumble commands to the Switch 2 Pro Controller via
multiple USB/HID methods that we haven't tested yet:
1. Interface 0 Interrupt OUT endpoint (if it exists)
2. USB Control Transfer (HID SET_REPORT)
3. hidapi library (if installed) via hid.write()

Usage:
    python tools/rumble_hid_control_test.py
"""

import sys
import time
import usb.core
import usb.util

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1

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

# Strong rumble data (both actuators max safe)
RUMBLE_DATA = bytes([
    0x74, 0xC8, 0x9C, 0x72,  # left actuator
    0x74, 0xC8, 0x9C, 0x72,  # right actuator
])
NEUTRAL_DATA = bytes([0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40])


def init_controller(dev, ep_out):
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


def main():
    print("=" * 70)
    print(" Switch 2 Pro Controller -- HID/Control Rumble Test")
    print("=" * 70)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)

    print("[OK ] Device found.")
    dev.set_configuration()
    cfg = dev.get_active_configuration()

    # -------------------------------------------------------------------
    # Examine Interface 1 (Bulk)
    # -------------------------------------------------------------------
    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    ep1_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep1_out = ep.bEndpointAddress
    print(f"[OK ] Interface 1 Bulk OUT: 0x{ep1_out:02X}")

    # -------------------------------------------------------------------
    # Examine Interface 0 (HID)
    # -------------------------------------------------------------------
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_in = None
    ep0_out = None
    for ep in intf0:
        dir_ = usb.util.endpoint_direction(ep.bEndpointAddress)
        if dir_ == usb.util.ENDPOINT_IN:
            ep0_in = ep.bEndpointAddress
            print(f"[OK ] Interface 0 Interrupt IN : 0x{ep0_in:02X}")
        elif dir_ == usb.util.ENDPOINT_OUT:
            ep0_out = ep.bEndpointAddress
            print(f"[OK ] Interface 0 Interrupt OUT: 0x{ep0_out:02X}")

    if ep0_out is None:
        print("[INFO] Interface 0 has no OUT endpoint (only IN).")

    # -------------------------------------------------------------------
    # Initialize
    # -------------------------------------------------------------------
    print("\n[INFO] Initializing controller...")
    init_controller(dev, ep1_out)
    print("[OK ] Initialization complete.")

    # -------------------------------------------------------------------
    # Helper: test a single packet via given method
    # -------------------------------------------------------------------
    def test_method(name, send_fn):
        print(f"\n[Test] {name}")
        user = input("    Press Enter to vibrate, or 'skip': ").strip().lower()
        if user == 'skip':
            print("    Skipped.")
            return
        try:
            ok = send_fn()
            if ok:
                print("    [OK ] Sent. Did it vibrate?")
                time.sleep(1.5)
                # Stop
                stop_fn()
                print("    [OK ] Stopped.")
            else:
                print("    [FAIL] Send returned False.")
        except Exception as e:
            print(f"    [ERROR] {e}")

    # -------------------------------------------------------------------
    # Method 1: Interface 0 Interrupt OUT (if it exists)
    # -------------------------------------------------------------------
    def send_via_int0_out():
        if ep0_out is None:
            return False
        try:
            usb.util.claim_interface(dev, 0)
            # Try two possible prefixes
            data = bytes([0x10, 0x00]) + RUMBLE_DATA  # with report ID
            dev.write(ep0_out, data)
            usb.util.release_interface(dev, 0)
            return True
        except usb.core.USBError:
            return False

    def stop_via_int0_out():
        if ep0_out is None:
            return
        try:
            usb.util.claim_interface(dev, 0)
            data = bytes([0x10, 0x00]) + NEUTRAL_DATA
            dev.write(ep0_out, data)
            usb.util.release_interface(dev, 0)
        except Exception:
            pass

    test_method("Interface 0 Interrupt OUT endpoint", send_via_int0_out)

    # -------------------------------------------------------------------
    # Method 2: USB Control Transfer (HID SET_REPORT)
    # -------------------------------------------------------------------
    def send_via_control():
        # bmRequestType=0x21 (HID class, host->device, interface)
        # bRequest=0x09 (SET_REPORT)
        # wValue=0x0210 (Output Report, Report ID 0x10)
        # wIndex=0 (Interface 0)
        # data = [ReportID, timer, rumble...]
        report = bytes([0x10, 0x00]) + RUMBLE_DATA
        try:
            dev.ctrl_transfer(0x21, 0x09, 0x0210, 0, report)
            return True
        except usb.core.USBError:
            # Try wValue=0x0200 (Output Report, Report ID 0)
            try:
                report = bytes([0x00, 0x10, 0x00]) + RUMBLE_DATA
                dev.ctrl_transfer(0x21, 0x09, 0x0200, 0, report)
                return True
            except usb.core.USBError:
                return False

    def stop_via_control():
        try:
            report = bytes([0x10, 0x00]) + NEUTRAL_DATA
            dev.ctrl_transfer(0x21, 0x09, 0x0210, 0, report)
        except Exception:
            pass

    test_method("USB Control Transfer (HID SET_REPORT)", send_via_control)

    # -------------------------------------------------------------------
    # Method 3: hidapi library (hid.write)
    # -------------------------------------------------------------------
    try:
        import hid
    except ImportError:
        print("\n[INFO] 'hid' library not installed (pip install hid), skipping hidapi test.")
        hid = None

    if hid:
        def send_via_hidapi():
            try:
                h = hid.device()
                h.open(TARGET_VID, TARGET_PID)
                # Output report: [ReportID=0x10, timer, rumble(8)]
                h.write(bytes([0x10, 0x00]) + RUMBLE_DATA)
                h.close()
                return True
            except Exception:
                return False

        def stop_via_hidapi():
            try:
                h = hid.device()
                h.open(TARGET_VID, TARGET_PID)
                h.write(bytes([0x10, 0x00]) + NEUTRAL_DATA)
                h.close()
            except Exception:
                pass

        test_method("hidapi (hid.write) -- may fail if driver is libusbK", send_via_hidapi)

    # -------------------------------------------------------------------
    # Method 4: Bulk OUT with 64-byte padded packet
    # -------------------------------------------------------------------
    def send_padded_bulk():
        try:
            usb.util.claim_interface(dev, USB_INTERFACE_NUMBER)
            # Some devices expect fixed-size reports (e.g. 64 bytes)
            payload = bytes([0x10, 0x00]) + RUMBLE_DATA
            padded = payload + bytes(64 - len(payload))
            dev.write(ep1_out, padded)
            usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
            return True
        except usb.core.USBError:
            return False

    def stop_padded_bulk():
        try:
            usb.util.claim_interface(dev, USB_INTERFACE_NUMBER)
            payload = bytes([0x10, 0x00]) + NEUTRAL_DATA
            padded = payload + bytes(64 - len(payload))
            dev.write(ep1_out, padded)
            usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
        except Exception:
            pass

    test_method("Interface 1 Bulk OUT with 64-byte padding", send_padded_bulk)

    # -------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------
    print("\n[INFO] Cleaning up...")
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass
    try:
        usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
    except Exception:
        pass
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Cancelled by user.")
        sys.exit(0)
