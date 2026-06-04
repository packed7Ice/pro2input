import sys
import time
import usb.core
import usb.util

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Interactive Mapping Tool
# ---------------------------------------------------------------------------
#  Reads data and highlights which bytes changed from the baseline.
#  Helps identify button/stick mappings.
# ---------------------------------------------------------------------------

TARGET_VID = 0x057E
TARGET_PID = 0x2069
USB_INTERFACE_NUMBER = 1

# Initialization Commands (from enable_hid.py)
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


def init_controller(dev):
    """Initialize the controller via Interface 1."""
    cfg = dev.get_active_configuration()
    intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
    
    ep_out = None
    for ep in intf1:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break
    
    if ep_out is None:
        raise RuntimeError("Bulk OUT endpoint not found")
    
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
    
    return cfg


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Interactive Mapping Tool")
    print("=" * 80)
    print("\n[INFO] This tool will capture the baseline (idle) state, then")
    print("       show changes when you press buttons or move sticks.")
    print("       Press Ctrl+C to stop.\n")

    dev = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
    if dev is None:
        print("[FATAL] Device not found.")
        sys.exit(1)
    
    dev.set_configuration()
    cfg = init_controller(dev)
    
    # Get Interface 0 endpoints
    intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    ep0_in = usb.util.find_descriptor(
        intf0,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )
    
    if ep0_in is None:
        print("[FATAL] Interrupt IN endpoint not found.")
        sys.exit(1)
    
    try:
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError:
        pass
    
    # Capture baseline - take multiple samples to account for IMU drift
    print("[CAPTURE] Capturing baseline samples...")
    print("          Please do NOT touch the controller for 2 seconds.\n")
    
    baseline_samples = []
    start_time = time.time()
    while time.time() - start_time < 2.0:
        try:
            data = dev.read(ep0_in.bEndpointAddress, 64, timeout=100)
            if data:
                baseline_samples.append(list(data))
        except usb.core.USBError:
            pass
    
    if len(baseline_samples) < 3:
        print("[FATAL] Could not capture enough baseline samples.")
        sys.exit(1)
    
    # Use the last sample as baseline (stabilized)
    baseline = baseline_samples[-1]
    
    print("[OK ] Baseline captured.\n")
    print("Baseline samples:")
    for i, sample in enumerate(baseline_samples[-3:]):
        hex_str = " ".join(f"{b:02X}" for b in sample)
        print(f"  Sample {i+1}: {hex_str}")
    print()
    
    # Identify stable vs changing bytes
    print("[ANALYSIS] Identifying byte stability...")
    stable_bytes = []
    changing_bytes = []
    for byte_idx in range(64):
        values = set(s[byte_idx] for s in baseline_samples)
        if len(values) == 1:
            stable_bytes.append(byte_idx)
        else:
            changing_bytes.append(byte_idx)
    
    print(f"  Stable bytes (likely buttons): {stable_bytes}")
    print(f"  Changing bytes (likely IMU/sticks): {changing_bytes}")
    print()
    
    print("=" * 80)
    print("[LIVE] Now press buttons or move sticks!")
    print("       Changed bytes will be highlighted.")
    print("       Note: IMU/stick bytes will change even without input.")
    print("=" * 80)
    
    try:
        while True:
            try:
                data = dev.read(ep0_in.bEndpointAddress, 64, timeout=100)
                if data:
                    current = list(data)
                    
                    # Build output with highlights
                    output_parts = []
                    for i in range(len(current)):
                        if i < len(baseline) and current[i] != baseline[i]:
                            output_parts.append(f"\033[91m{current[i]:02X}\033[0m")  # Red
                        else:
                            output_parts.append(f"{current[i]:02X}")
                    
                    hex_str = " ".join(output_parts)
                    
                    # Show changed bytes summary (only for stable/interesting bytes)
                    changed = [f"Byte{i}={current[i]:02X}(was {baseline[i]:02X})" 
                               for i in range(min(len(current), len(baseline))) 
                               if current[i] != baseline[i] and i in stable_bytes]
                    
                    if changed:
                        print(f"\nRECV: {hex_str}")
                        print(f"      BUTTON CHANGES: {', '.join(changed)}")
                    else:
                        # Only print every 30 frames to avoid spam
                        pass
            except usb.core.USBError:
                pass
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass
    
    print("Done.")


if __name__ == "__main__":
    main()
