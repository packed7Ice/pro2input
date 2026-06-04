"""
tools/rumble_hid_control_test.py

Sends rumble commands to the Switch 2 Pro Controller via
Interface 0 Interrupt OUT endpoint (0x01) with the SDL-derived format.

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
    # FIXED: SDL validated "enable rumble" command (was incorrectly 0x10)
    bytes([0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x03, 0x00, 0x00]),
    bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
]

# SDL defaults
HF_FREQ = 0x0187
LF_FREQ = 0x0112
AMP_MAX = 29000


def encode_actuator(high_freq, high_amp, low_freq, low_amp):
    """SDL EncodeHDRumble logic."""
    data = bytearray(5)
    data[0] = high_freq & 0xFF
    data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
    data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
    data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
    data[4] = (low_amp >> 8) & 0xFF
    return bytes(data)


def build_rumble_report(seq, hf_amp, lf_amp):
    """Build 64-byte Switch 2 Pro rumble output report."""
    actuator = encode_actuator(HF_FREQ, hf_amp, LF_FREQ, lf_amp)
    seq_byte = 0x50 | (seq & 0x0F)
    report = bytearray(64)
    report[0] = 0x02
    report[1] = seq_byte
    report[2:7] = actuator
    report[17] = seq_byte
    report[18:23] = actuator
    return bytes(report)


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
    print(" Switch 2 Pro Controller -- Interface 0 OUT Rumble Test")
    print(" Uses SDL-derived 64-byte report via Interrupt OUT endpoint")
    print("=" * 70)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)

    print("[OK ] Device found.")
    dev.set_configuration()
    cfg = dev.get_active_configuration()

    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    ep1_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep1_out = ep.bEndpointAddress
    print(f"[OK ] Interface 1 Bulk OUT: 0x{ep1_out:02X}")

    # Find Interface 0 endpoints
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_in = None
    ep0_out = None
    for ep in intf0:
        dir_ = usb.util.endpoint_direction(ep.bEndpointAddress)
        if dir_ == usb.util.ENDPOINT_IN:
            ep0_in = ep
            print(f"[OK ] Interface 0 Interrupt IN : 0x{ep.bEndpointAddress:02X}")
        elif dir_ == usb.util.ENDPOINT_OUT:
            ep0_out = ep
            print(f"[OK ] Interface 0 Interrupt OUT: 0x{ep.bEndpointAddress:02X}")

    print("\n[INFO] Initializing controller...")
    init_controller(dev, ep1_out)
    print("[OK ] Initialization complete.")

    # Claim Interface 0 for output writes
    try:
        usb.util.claim_interface(dev, 0)
        print("[OK ] Interface 0 claimed for output.")
    except usb.core.USBError:
        pass

    seq = 0

    def send_vibrate():
        nonlocal seq
        seq += 1
        report = build_rumble_report(seq, AMP_MAX, AMP_MAX)
        print(f"    Sending 64-byte report [seq=0x{seq & 0x0F:01X}] to 0x{ep0_out.bEndpointAddress:02X}...")
        try:
            dev.write(ep0_out.bEndpointAddress, report)
            return True
        except usb.core.USBError as e:
            print(f"    [FAIL] {e}")
            return False

    def send_stop():
        nonlocal seq
        seq += 1
        neutral = encode_actuator(HF_FREQ, 0, LF_FREQ, 0)
        seq_byte = 0x50 | (seq & 0x0F)
        report = bytearray(64)
        report[0] = 0x02
        report[1] = seq_byte
        report[2:7] = neutral
        report[17] = seq_byte
        report[18:23] = neutral
        try:
            dev.write(ep0_out.bEndpointAddress, bytes(report))
        except Exception:
            pass

    print("\n" + "=" * 70)
    print(" Press Enter to send vibration (max amplitude)")
    print(" Type 'quit' to exit")
    print("=" * 70)

    while True:
        user = input("\n> ").strip().lower()
        if user == 'quit':
            break
        if user == '':
            ok = send_vibrate()
            if ok:
                print("    [OK ] Vibration sent. Did the controller vibrate?")
                time.sleep(1.5)
                send_stop()
                print("    [OK ] Stopped.")

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
