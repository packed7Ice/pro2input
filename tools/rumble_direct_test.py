"""
tools/rumble_direct_test.py

Sends raw USB rumble commands directly to the Switch 2 Pro Controller
using multiple candidate command formats.  Helps identify which
format the Switch 2 Pro actually responds to.

Usage:
    python tools/rumble_direct_test.py

The script will initialize the controller, then prompt you to press Enter
to try each candidate rumble format.  Report whether the controller vibrated.
"""

import sys
import time
import usb.core
import usb.util

# ---------------------------------------------------------------------------
# Device constants (copied from core.constants to be self-contained)
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

# Rumble data: strong vibration on both actuators
# Based on Nintendo Switch Pro Controller rumble encoding.
# HF ~600Hz amp=max_safe, LF ~260Hz amp=max_safe
RUMBLE_DATA = bytes([
    0x74, 0xC8,  # Left  HF freq+amp
    0x9C, 0x72,  # Left  LF freq+amp
    0x74, 0xC8,  # Right HF freq+amp
    0x9C, 0x72,  # Right LF freq+amp
])

# Neutral (no vibration)
NEUTRAL_DATA = bytes([0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40])


def init_controller(dev, ep_out):
    """Send the standard initialization sequence."""
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


def send_rumble_cmd(dev, ep_out, cmd: bytes) -> bool:
    """Claim interface, send command, release interface."""
    try:
        usb.util.claim_interface(dev, USB_INTERFACE_NUMBER)
        dev.write(ep_out, cmd)
        usb.util.release_interface(dev, USB_INTERFACE_NUMBER)
        return True
    except usb.core.USBError as e:
        print(f"  [USB Error] {e}")
        return False


def main():
    print("=" * 70)
    print(" Switch 2 Pro Controller -- Direct USB Rumble Test")
    print("=" * 70)
    print("\n[INFO] Connect your Switch 2 Pro Controller via USB.")
    print("       During each test, the script will send a rumble command.")
    print("       Press Enter to proceed, or type 'skip' to skip a format.")
    print("       Type 'quit' at any prompt to exit.\n")

    # -----------------------------------------------------------------------
    # Find device
    # -----------------------------------------------------------------------
    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)

    print("[OK ] Device found.")
    dev.set_configuration()
    cfg = dev.get_active_configuration()

    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    if intf1 is None:
        print("[FATAL] Interface 1 not found.")
        sys.exit(1)

    ep_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break

    if ep_out is None:
        print("[FATAL] Bulk OUT endpoint not found on Interface 1.")
        sys.exit(1)

    print("[OK ] Bulk OUT endpoint: 0x%02X" % ep_out)

    # -----------------------------------------------------------------------
    # Initialize controller
    # -----------------------------------------------------------------------
    print("\n[INFO] Sending initialization sequence...")
    init_controller(dev, ep_out)
    print("[OK ] Initialization complete.")

    # -----------------------------------------------------------------------
    # Candidate rumble command formats to test
    # -----------------------------------------------------------------------
    timer = 0x00

    candidates = [
        ("Format A: [0x10, 0x91, 0x00, timer, rumble(8)]  (current main.py format)",
         lambda t: bytes([0x10, 0x91, 0x00, t]) + RUMBLE_DATA),

        ("Format B: [0x10, timer, rumble(8)]  (raw BT HID OUTPUT 0x10)",
         lambda t: bytes([0x10, t]) + RUMBLE_DATA),

        ("Format C: [0x01, timer, rumble(8)]  (raw BT HID OUTPUT 0x01 no subcmd)",
         lambda t: bytes([0x01, t]) + RUMBLE_DATA),

        ("Format D: [0x10, 0x91, 0x00, 0x01, 0x00,0x00,0x00,0x00, rumble(8)]  (extend init 0x10 cmd)",
         lambda t: bytes([0x10, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]) + RUMBLE_DATA),

        ("Format E: [0x03, 0x91, 0x00, 0x0A, rumble(8)]  (ENABLE_HAPTICS-like header)",
         lambda t: bytes([0x03, 0x91, 0x00, 0x0A]) + RUMBLE_DATA),

        ("Format F: [0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, rumble(8)]  (0x09 header)",
         lambda t: bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00]) + RUMBLE_DATA),

        ("Format G: [0x0A, 0x91, 0x00, 0x08, ..., rumble(8)]  (0x0A long header)",
         lambda t: bytes([0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01,
                          0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                          0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00,
                          0x00, 0x00, 0x00]) + RUMBLE_DATA),

        ("Format H: [0x10, 0x91, timer, 0x01, rumble(8)]  (timer shifted)",
         lambda t: bytes([0x10, 0x91, t, 0x01]) + RUMBLE_DATA),

        ("Format I: [0x10, 0x91, 0x00, 0x01, timer, rumble(8)]  (init-style + timer + rumble)",
         lambda t: bytes([0x10, 0x91, 0x00, 0x01, t]) + RUMBLE_DATA),

        ("Format J: [0x00, timer, rumble(8)]  (report ID 0x00)",
         lambda t: bytes([0x00, t]) + RUMBLE_DATA),
    ]

    print("\n" + "=" * 70)
    print(" Starting rumble format tests")
    print("=" * 70)

    for i, (desc, builder) in enumerate(candidates, 1):
        print(f"\n[Test {i}/{len(candidates)}] {desc}")
        user = input("    Press Enter to send, or type 'skip' / 'quit': ").strip().lower()

        if user == 'quit':
            print("[INFO] Exiting.")
            break
        if user == 'skip':
            print("    Skipped.")
            continue

        cmd = builder(timer)
        timer = (timer + 1) & 0xFF
        print(f"    Sending {len(cmd)} bytes: {cmd.hex()}")

        ok = send_rumble_cmd(dev, ep_out, cmd)
        if ok:
            print("    [OK ] Command sent. Did the controller vibrate?")
            time.sleep(1.5)
            # Send neutral to stop
            neutral_cmd = bytes([0x10, 0x91, 0x00, 0x00]) + NEUTRAL_DATA
            send_rumble_cmd(dev, ep_out, neutral_cmd)
            print("    [OK ] Neutral sent (vibration stopped).")
        else:
            print("    [FAIL] Send failed.")

    # Cleanup
    print("\n[INFO] Releasing interfaces...")
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
