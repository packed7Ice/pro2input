"""
tools/rumble_comprehensive_test.py

Comprehensive rumble test for Switch 2 Pro Controller.
Tests multiple approaches to find what actually triggers vibration.

Approach order (each needs Enter to run):
  1. Extended init (with 0x15/0x16 haptic commands) + Bulk OUT [0x02 report]
  2. Extended init + USB Control Transfer SET_REPORT [0x02 report]
  3. Wrapped rumble via 0x91 header (same format as init commands)
  4. Old Switch Pro 8-byte format via Bulk OUT [0x10 report]

Run with controller freshly connected (no other process holding Interface 1).
Interface 0 should use Windows HID; Interface 1 should use libusbK.
"""

import sys
import time
import usb.core
import usb.util

TARGET_VID = 0x057E
TARGET_PID = 0x2069
INTF = 1
BULK_TIMEOUT = 1000

# ---------------------------------------------------------------------------
# Extended init sequence (includes 0x15/0x16 haptic commands missing from
# the main constants.py).  These three 0x15 commands configure haptic engine.
# ---------------------------------------------------------------------------
READ_FLASH = []


def _flash_cmd(addr):
    c = bytearray(16)
    c[0]=0x02; c[1]=0x91; c[2]=0x00; c[3]=0x01; c[5]=0x08
    c[12]=addr&0xFF; c[13]=(addr>>8)&0xFF; c[14]=(addr>>16)&0xFF; c[15]=(addr>>24)&0xFF
    return bytes(c)


READ_FLASH = [_flash_cmd(a) for a in [0x13000, 0x13040, 0x13080, 0x130C0, 0x13100]]

# Extended init: includes 0x15/0x16 haptic-configure commands
INIT_EXTENDED = [
    bytes([0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x11, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0A, 0x91, 0x00, 0x08, 0x00, 0x14, 0x00, 0x00, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x35, 0x00, 0x46, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x0C, 0x91, 0x00, 0x04, 0x00, 0x04, 0x00, 0x00, 0x27, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x01, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),  # Enable rumble
    bytes([0x08, 0x91, 0x00, 0x02, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0A, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0D, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    # ---- Haptic configuration commands (0x15/0x16) ----
    bytes([0x16, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x15, 0x91, 0x00, 0x01, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x02, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x15, 0x91, 0x00, 0x02, 0x00, 0x11, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x15, 0x91, 0x00, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00]),
]

LED_CMD = bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

HF_FREQ = 0x0187
LF_FREQ = 0x0112
AMP_MAX = 29000


def encode_actuator(hf, hf_amp, lf, lf_amp):
    d = bytearray(5)
    d[0] = hf & 0xFF
    d[1] = ((hf_amp >> 4) & 0xFC) | ((hf >> 8) & 0x03)
    d[2] = (hf_amp >> 12) | ((lf << 4) & 0xFF)
    d[3] = (lf_amp & 0xC0) | ((lf >> 4) & 0x3F)
    d[4] = (lf_amp >> 8) & 0xFF
    return bytes(d)


def build_report_0x02(seq, amp):
    """64-byte report with report ID 0x02 and SDL-correct offsets."""
    act = encode_actuator(HF_FREQ, amp, LF_FREQ, amp)
    seq_b = 0x50 | (seq & 0x0F)
    r = bytearray(64)
    r[0] = 0x02
    r[1] = seq_b
    r[2:7] = act
    r[17] = seq_b      # SDL: 0x11 = 17
    r[18:23] = act     # SDL: 0x12..0x16
    return bytes(r)


def build_report_0x10_8byte(seq, amp):
    """10-byte report: 0x10 header + 8-byte old Switch Pro rumble."""
    # Old Switch Pro (BT) format: 4 bytes per actuator, 2-byte pairs
    # Scale: amp/29000 * max
    a = min(255, int(amp / 29000 * 255))
    rumble = bytes([a, 0x00, a, 0x00, a, 0x00, a, 0x00])
    return bytes([0x10, seq & 0xFF]) + rumble


def build_report_wrapped_0x91(seq, amp):
    """
    Rumble wrapped in 0x91 protocol header (same format as init commands).
    Hypothesis: maybe rumble uses CMD=0x02 with sub like 0x0D 'Start output'.
    """
    act = encode_actuator(HF_FREQ, amp, LF_FREQ, amp)
    # CMD=0x03 (output), sub=0x0D (start output), data=[seq, 0x00, actuator×2]
    data = bytes([0x01, seq & 0xFF]) + act + act  # 12 bytes
    length = len(data)
    header = bytes([0x03, 0x91, 0x00, 0x0D, 0x00, length, 0x00, 0x00])
    return header + data


# ---------------------------------------------------------------------------
# USB helper
# ---------------------------------------------------------------------------

def do_init(dev, ep_out, ep_in, use_flash=True, use_extended=True):
    def w(data, label=""):
        try:
            dev.write(ep_out, data, timeout=BULK_TIMEOUT)
            if label:
                print(f"    [OK ] {label}")
        except usb.core.USBError as e:
            if label:
                print(f"    [ERR] {label}: {e}")

    def r():
        if ep_in is None:
            return
        try:
            dev.read(ep_in, 64, timeout=100)
        except usb.core.USBError:
            pass

    if use_flash:
        print("  ReadFlash...")
        for cmd in READ_FLASH:
            w(cmd); time.sleep(0.05); r()

    print("  Init commands...")
    cmds = INIT_EXTENDED if use_extended else []
    for cmd in cmds:
        send_len = cmd[5] + 8 if len(cmd) > 5 else len(cmd)
        send_len = min(send_len, len(cmd))
        w(cmd[:send_len])
        time.sleep(0.05)
        r()

    w(LED_CMD, "LED")
    time.sleep(0.05); r()


def burst_send(dev, ep_out, build_fn, duration=2.0, interval=0.015):
    """Send rumble packets for `duration` seconds."""
    seq = 0
    sent = 0
    errors = 0
    end_t = time.time() + duration
    while time.time() < end_t:
        pkt = build_fn(seq)
        seq = (seq + 1) & 0x0F
        try:
            dev.write(ep_out, pkt, timeout=BULK_TIMEOUT)
            sent += 1
        except usb.core.USBError as e:
            errors += 1
            if errors <= 3:
                print(f"    [WARN] {e}")
        time.sleep(interval)
    return sent, errors


def try_control_transfer(dev, report, interface=0):
    """
    HID SET_REPORT via USB control transfer (Endpoint 0).
    Works regardless of which driver owns Interface 0 or 1.
    bmRequestType=0x21 bRequest=0x09 wValue=0x0202 wIndex=interface
    """
    try:
        dev.ctrl_transfer(
            0x21,           # bmRequestType: Host→Device, Class, Interface
            0x09,           # bRequest: HID SET_REPORT
            0x0200 | report[0],  # wValue: Output report (0x02xx), report ID in low byte
            interface,      # wIndex: interface
            report,         # data
            timeout=500,
        )
        return True, None
    except usb.core.USBError as e:
        return False, e


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print(" Switch 2 Pro -- Comprehensive Rumble Test")
    print(" Tests multiple formats and transports to find what vibrates")
    print("=" * 70)

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)
    print("[OK ] Device found.")

    dev.set_configuration()
    cfg = dev.get_active_configuration()

    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=INTF)
    ep_out = None; ep_in = None
    for ep in intf1:
        d = usb.util.endpoint_direction(ep.bEndpointAddress)
        if d == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
        elif d == usb.util.ENDPOINT_IN:
            ep_in = ep.bEndpointAddress

    if ep_out is None:
        print("[FATAL] Bulk OUT not found."); sys.exit(1)
    print(f"[OK ] Interface 1  Bulk OUT=0x{ep_out:02X}  Bulk IN={('0x%02X'%ep_in) if ep_in else 'N/A'}")

    # Enumerate Interface 0 endpoints
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_out = None
    if intf0:
        for ep in intf0:
            d = usb.util.endpoint_direction(ep.bEndpointAddress)
            t = usb.util.endpoint_type(ep.bmAttributes)
            label = "OUT" if d == usb.util.ENDPOINT_OUT else "IN "
            tname = {
                usb.util.ENDPOINT_TYPE_BULK: "Bulk",
                usb.util.ENDPOINT_TYPE_INTR: "Intr",
                usb.util.ENDPOINT_TYPE_ISO:  "Iso ",
                usb.util.ENDPOINT_TYPE_CTRL: "Ctrl",
            }.get(t, "?")
            print(f"[OK ] Interface 0  ep=0x{ep.bEndpointAddress:02X} {label} {tname}")
            if d == usb.util.ENDPOINT_OUT:
                ep0_out = ep.bEndpointAddress

    try:
        usb.util.claim_interface(dev, INTF)
    except usb.core.USBError:
        pass

    def ask(prompt):
        r = input(f"\n  {prompt} [Enter=run / s=skip / q=quit]: ").strip().lower()
        if r == 'q':
            cleanup(dev)
            print("Bye.")
            sys.exit(0)
        return r != 's'

    def report_result():
        ans = input("  Vibrated? [y/n]: ").strip().lower()
        return ans == 'y'

    # =========================================================================
    # Test 1: Extended init + Bulk OUT, report ID 0x02
    # =========================================================================
    print("\n" + "="*70)
    print("Test 1: Extended init (with 0x15/0x16) + Bulk OUT, report ID 0x02")
    print("  Hypothesis: missing haptic-config commands prevent vibration")
    print("="*70)
    if ask("Run Test 1?"):
        print("  Running extended init...")
        do_init(dev, ep_out, ep_in, use_flash=True, use_extended=True)
        print("  Sending strong rumble for 2s...")
        sent, errs = burst_send(dev, ep_out, lambda s: build_report_0x02(s, AMP_MAX))
        print(f"  Sent {sent} packets, {errs} errors.")
        if report_result():
            print("  SUCCESS! Extended init + Bulk OUT works.")
        else:
            print("  Still no vibration. Continuing...")

    # =========================================================================
    # Test 2: Control Transfer (HID SET_REPORT), report ID 0x02
    # =========================================================================
    print("\n" + "="*70)
    print("Test 2: USB Control Transfer (HID SET_REPORT), report ID 0x02")
    print("  Transport: Endpoint 0 (default control), bypasses HID driver")
    print("="*70)
    if ask("Run Test 2?"):
        seq = 0
        sent = 0; errs = 0
        end_t = time.time() + 2.0
        print("  Sending via control transfer for 2s...")
        while time.time() < end_t:
            pkt = build_report_0x02(seq, AMP_MAX)
            seq = (seq + 1) & 0x0F
            ok, err = try_control_transfer(dev, pkt, interface=0)
            if ok:
                sent += 1
            else:
                errs += 1
                if errs <= 3:
                    print(f"    [WARN] {err}")
            time.sleep(0.015)
        print(f"  Sent {sent} OK, {errs} errors.")
        if report_result():
            print("  SUCCESS! Control Transfer works.")
        else:
            print("  Still no vibration.")

    # =========================================================================
    # Test 3: Wrapped 0x91 format (rumble inside Nintendo's Bulk protocol)
    # =========================================================================
    print("\n" + "="*70)
    print("Test 3: Rumble wrapped in 0x91 protocol header (CMD=0x03 sub=0x0D)")
    print("  Hypothesis: rumble uses the same wire format as init commands")
    print("="*70)
    if ask("Run Test 3?"):
        seq = 0
        sent = 0; errs = 0
        end_t = time.time() + 2.0
        print("  Sending wrapped rumble for 2s...")
        while time.time() < end_t:
            pkt = build_report_wrapped_0x91(seq, AMP_MAX)
            seq = (seq + 1) & 0x0F
            try:
                dev.write(ep_out, pkt, timeout=BULK_TIMEOUT)
                sent += 1
            except usb.core.USBError as e:
                errs += 1
                if errs <= 3:
                    print(f"    [WARN] {e}")
            time.sleep(0.015)
        print(f"  Sent {sent} OK, {errs} errors.")
        if report_result():
            print("  SUCCESS! 0x91-wrapped format works.")
        else:
            print("  Still no vibration.")

    # =========================================================================
    # Test 4: Old 8-byte rumble format (0x10 report ID)
    # =========================================================================
    print("\n" + "="*70)
    print("Test 4: Old Switch Pro 8-byte rumble, report ID 0x10 via Bulk OUT")
    print("  Hypothesis: Switch 2 Pro accepts old format over USB Bulk")
    print("="*70)
    if ask("Run Test 4?"):
        seq = 0
        sent, errs = burst_send(dev, ep_out, lambda s: build_report_0x10_8byte(s, AMP_MAX))
        print(f"  Sent {sent} packets, {errs} errors.")
        if report_result():
            print("  SUCCESS! Old 8-byte format works.")
        else:
            print("  Still no vibration.")

    # =========================================================================
    # Test 5: Interface 0 OUT endpoint (if accessible)
    # =========================================================================
    if ep0_out is not None:
        print("\n" + "="*70)
        print(f"Test 5: Interface 0 OUT endpoint (0x{ep0_out:02X})")
        print("  Note: Requires Interface 0 claimed (may fail if Windows HID owns it)")
        print("="*70)
        if ask("Run Test 5?"):
            claimed0 = False
            try:
                usb.util.claim_interface(dev, 0)
                claimed0 = True
                print("  [OK ] Interface 0 claimed.")
            except usb.core.USBError as e:
                print(f"  [SKIP] Cannot claim Interface 0: {e}")
                print("  (Interface 0 is under Windows HID driver — expected)")

            if claimed0:
                seq = 0
                sent, errs = burst_send(dev, ep0_out, lambda s: build_report_0x02(s, AMP_MAX))
                print(f"  Sent {sent} packets, {errs} errors.")
                if report_result():
                    print("  SUCCESS! Interface 0 OUT works.")
                else:
                    print("  Still no vibration.")
                try:
                    usb.util.release_interface(dev, 0)
                except Exception:
                    pass

    # =========================================================================
    print("\n" + "="*70)
    print("All tests complete.")
    print("If none vibrated: recommend USB packet capture (Wireshark + USBPcap)")
    print("to capture SDL's actual traffic when a game triggers rumble.")
    cleanup(dev)


def cleanup(dev):
    try:
        usb.util.release_interface(dev, INTF)
    except Exception:
        pass
    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
