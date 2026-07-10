"""
Stick raw value diagnostic — uses the SAME production connect/init path as
main.py (core.controller_usb.Switch2ProControllerUSB) so the byte offsets
match exactly what the real app sees.
"""
import sys
import time

sys.path.insert(0, ".")

from core.controller_usb import Switch2ProControllerUSB
from core.input_parser import unpack_12bit_triplet


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller -- Stick Raw Value Diagnostic (production path)")
    print("=" * 80)
    print("\n[INFO] Move sticks in full circles, holding each extreme for a second.")
    print("       Press Ctrl+C to stop.\n")

    controller = Switch2ProControllerUSB()
    if not controller.find_and_connect():
        print("[FATAL] Device not found.")
        sys.exit(1)
    controller.initialize_hid_mode()
    print("[OK] Connected via production init path.\n")

    lmin = [4095, 4095]
    lmax = [0, 0]
    rmin = [4095, 4095]
    rmax = [0, 0]

    counter = 0
    last_print = 0.0
    try:
        while True:
            payload = controller.read_input(timeout=100)
            if payload is None:
                continue
            lx_raw, ly_raw = unpack_12bit_triplet(payload[10:13])
            rx_raw, ry_raw = unpack_12bit_triplet(payload[13:16])

            lmin[0] = min(lmin[0], lx_raw); lmax[0] = max(lmax[0], lx_raw)
            lmin[1] = min(lmin[1], ly_raw); lmax[1] = max(lmax[1], ly_raw)
            rmin[0] = min(rmin[0], rx_raw); rmax[0] = max(rmax[0], rx_raw)
            rmin[1] = min(rmin[1], ry_raw); rmax[1] = max(rmax[1], ry_raw)

            now = time.time()
            if now - last_print >= 0.2:
                last_print = now
                hexdump = " ".join(f"{b:02X}" for b in payload[4:24])
                print(
                    f"LX={lx_raw:4d} LY={ly_raw:4d} | RX={rx_raw:4d} RY={ry_raw:4d}  "
                    f"raw[4:24]={hexdump}"
                )
    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")
    finally:
        print(f"Final ranges: LX=[{lmin[0]},{lmax[0]}] LY=[{lmin[1]},{lmax[1]}] "
              f"RX=[{rmin[0]},{rmax[0]}] RY=[{rmin[1]},{rmax[1]}]")
        controller.cleanup()
        print("Done.")


if __name__ == "__main__":
    main()
