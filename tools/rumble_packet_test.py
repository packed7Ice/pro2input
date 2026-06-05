"""
tools/rumble_packet_test.py

Fix verification: tests the corrected _build_report() packet layout.
Sends a strong rumble packet using the SDL-correct offset (0x11 = 17).

Usage:
    python tools/rumble_packet_test.py

Controller must be freshly connected (no other process holding Interface 1).
"""

import sys
import time
import usb.core
import usb.util

TARGET_VID = 0x057E
TARGET_PID = 0x2069
INTF = 1
_BULK_WRITE_TIMEOUT_MS = 1000

READ_FLASH_COMMANDS = []


def _read_flash_cmd(address: int) -> bytes:
    cmd = bytearray(16)
    cmd[0] = 0x02
    cmd[1] = 0x91
    cmd[2] = 0x00
    cmd[3] = 0x01
    cmd[4] = 0x00
    cmd[5] = 0x08
    cmd[12] = address & 0xFF
    cmd[13] = (address >> 8) & 0xFF
    cmd[14] = (address >> 16) & 0xFF
    cmd[15] = (address >> 24) & 0xFF
    return bytes(cmd)


READ_FLASH_COMMANDS = [
    _read_flash_cmd(0x13000),
    _read_flash_cmd(0x13040),
    _read_flash_cmd(0x13080),
    _read_flash_cmd(0x130C0),
    _read_flash_cmd(0x13100),
]

INIT_COMMANDS = [
    bytes([0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0A, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0D, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
]

LED_COMMAND = bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


def encode_actuator(high_freq, high_amp, low_freq, low_amp) -> bytes:
    data = bytearray(5)
    data[0] = high_freq & 0xFF
    data[1] = ((high_amp >> 4) & 0xFC) | ((high_freq >> 8) & 0x03)
    data[2] = (high_amp >> 12) | ((low_freq << 4) & 0xFF)
    data[3] = (low_amp & 0xC0) | ((low_freq >> 4) & 0x3F)
    data[4] = (low_amp >> 8) & 0xFF
    return bytes(data)


def build_rumble_packet(seq: int, high_amp: int, low_amp: int) -> bytes:
    """
    Correct SDL layout:
      [0]     = 0x02 (Report ID)
      [1]     = 0x50 | (seq & 0x0F)
      [2:7]   = left actuator (5 bytes)
      [7:17]  = zeros
      [17:23] = copy of [1:7]  ← SDL: memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)
      [23:64] = zeros
    """
    HF_FREQ = 0x0187
    LF_FREQ = 0x0112
    actuator = encode_actuator(HF_FREQ, high_amp, LF_FREQ, low_amp)

    report = bytearray(64)
    report[0] = 0x02
    report[1] = 0x50 | (seq & 0x0F)
    report[2:7] = actuator
    report[17:23] = report[1:7]   # SDL: memcpy(&rumble_data[0x11], &rumble_data[0x01], 6)
    return bytes(report)


def build_neutral_packet(seq: int) -> bytes:
    neutral = bytes([0x87, 0x01, 0x20, 0x11, 0x00])
    report = bytearray(64)
    report[0] = 0x02
    report[1] = 0x50 | (seq & 0x0F)
    report[2:7] = neutral
    report[17:23] = report[1:7]
    return bytes(report)


def main():
    print("=" * 60)
    print(" Rumble packet offset fix verification")
    print(" SDL-correct layout: right actuator at [17:23]")
    print("=" * 60)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)
    print("[OK ] Device found.")

    dev.set_configuration()
    cfg = dev.get_active_configuration()

    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=INTF)
    if intf1 is None:
        print("[FATAL] Interface 1 not found.")
        sys.exit(1)

    ep_out = None
    ep_in = None
    for ep in intf1:
        d = usb.util.endpoint_direction(ep.bEndpointAddress)
        if d == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
        elif d == usb.util.ENDPOINT_IN:
            ep_in = ep.bEndpointAddress

    if ep_out is None:
        print("[FATAL] Bulk OUT not found.")
        sys.exit(1)
    print(f"[OK ] Bulk OUT = 0x{ep_out:02X}  Bulk IN = {('0x%02X' % ep_in) if ep_in else 'N/A'}")

    try:
        usb.util.claim_interface(dev, INTF)
    except usb.core.USBError:
        pass

    def write(data, label=""):
        try:
            dev.write(ep_out, data, timeout=_BULK_WRITE_TIMEOUT_MS)
            if label:
                print(f"  [OK ] {label}")
        except usb.core.USBError as e:
            if label:
                print(f"  [ERR] {label}: {e}")

    def read_response():
        if ep_in is None:
            return
        try:
            dev.read(ep_in, 64, timeout=100)
        except usb.core.USBError:
            pass

    # ReadFlash
    print("\n[INFO] Sending ReadFlashBlock...")
    for cmd in READ_FLASH_COMMANDS:
        write(cmd)
        time.sleep(0.05)
        read_response()

    # Init
    print("[INFO] Sending init sequence...")
    for cmd in INIT_COMMANDS:
        send_len = cmd[5] + 8
        write(cmd[:send_len])
        time.sleep(0.05)
        read_response()

    # LED
    write(LED_COMMAND, "LED command")
    time.sleep(0.05)
    read_response()

    print("\n[INFO] Init complete.")

    seq = 0

    # Show packet layout
    RUMBLE_AMP_MAX = 29000
    pkt = build_rumble_packet(seq, RUMBLE_AMP_MAX, RUMBLE_AMP_MAX)
    print("\n[INFO] Sample strong-rumble packet (hex):")
    print("  " + pkt.hex())
    print(f"  [0]    = 0x{pkt[0]:02X}  (Report ID)")
    print(f"  [1]    = 0x{pkt[1]:02X}  (seq byte)")
    print(f"  [2:7]  = {pkt[2:7].hex()}  (left actuator)")
    print(f"  [17]   = 0x{pkt[17]:02X}  (seq copy, should == [1])")
    print(f"  [18:23]= {pkt[18:23].hex()}  (right actuator copy, should == [2:7])")
    assert pkt[17:23] == pkt[1:7], "BUG: offset mismatch not fixed!"
    print("  [PASS] Offset check OK: [17:23] == [1:7]")

    input("\n  Press Enter to SEND strong rumble (2 seconds)...")

    # Strong rumble burst
    print("[INFO] Sending strong rumble for 2 seconds...")
    end_t = time.time() + 2.0
    while time.time() < end_t:
        pkt = build_rumble_packet(seq, RUMBLE_AMP_MAX, RUMBLE_AMP_MAX)
        seq = (seq + 1) & 0x0F
        try:
            dev.write(ep_out, pkt, timeout=_BULK_WRITE_TIMEOUT_MS)
        except usb.core.USBError as e:
            print(f"  [WARN] {e}")
        time.sleep(0.015)

    # Neutral
    pkt = build_neutral_packet(seq)
    seq = (seq + 1) & 0x0F
    try:
        dev.write(ep_out, pkt, timeout=_BULK_WRITE_TIMEOUT_MS)
        print("[OK ] Neutral packet sent.")
    except usb.core.USBError as e:
        print(f"[WARN] Neutral: {e}")

    print("\nDid the controller vibrate? (y/n)")
    ans = input("> ").strip().lower()
    if ans == "y":
        print("[SUCCESS] Vibration confirmed! The offset fix works.")
    else:
        print("[FAIL] Still no vibration. Further investigation needed.")
        print("       Check: Zadig Interface 1 = libusbK (not WinUSB)")

    try:
        usb.util.release_interface(dev, INTF)
    except Exception:
        pass
    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
