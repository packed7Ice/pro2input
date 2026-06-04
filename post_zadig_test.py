import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Post-Zadig Direct Path Test
# ---------------------------------------------------------------------------
#  Uses device paths discovered from registry after Zadig driver replacement.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32


def open_device(path):
    """Open device with read/write access."""
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
        0x00000001 | 0x00000002,    # FILE_SHARE_READ | FILE_SHARE_WRITE
        None,
        3,                          # OPEN_EXISTING
        0,
        None
    )
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def write_device(handle, data, report_size=64):
    """Write raw bytes padded to report_size."""
    if len(data) < report_size:
        data = data + [0] * (report_size - len(data))
    elif len(data) > report_size:
        data = data[:report_size]
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = wintypes.DWORD(0)
    ret = kernel32.WriteFile(handle, buf, len(data), ctypes.byref(written), None)
    if not ret:
        print(f"  [WARN] WriteFile failed. Error: {kernel32.GetLastError()}")
        return False
    return True


def read_device(handle, size, timeout_ms=5000):
    """Read raw bytes from device."""
    buf = (ctypes.c_ubyte * size)()
    read_count = wintypes.DWORD(0)
    ret = kernel32.ReadFile(handle, buf, size, ctypes.byref(read_count), None)
    if ret:
        return bytes(buf[:read_count.value])
    return None


def test_path(path, label):
    """Try to open a path and initialize the controller."""
    print(f"\n[TRY] {label}")
    print(f"      Path: {path}")
    
    handle = open_device(path)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[NG ] CreateFile failed. Error: {err}")
        return False
    
    print(f"[OK ] Handle opened: {handle}")
    
    # Try various init sequences
    candidates = [
        ("64-byte zeros", [0x00] * 64),
        ("Handshake 0x80 0x01", [0x80, 0x01] + [0x00] * 62),
        ("Handshake 0x80 0x02", [0x80, 0x02] + [0x00] * 62),
        ("Report Mode 0x3F", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x3F] + [0x00] * 52),
        ("Report Mode 0x30", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x30] + [0x00] * 52),
    ]
    
    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_device(handle, payload):
            time.sleep(0.3)
            peek = read_device(handle, 64, timeout_ms=500)
            if peek:
                print(f"  [OK ] Controller responded ({len(peek)} bytes)!")
                
                print("\n" + "=" * 80)
                print("[READ] Entering main read loop. Press Ctrl+C to stop.")
                print("=" * 80)
                
                last = None
                try:
                    while True:
                        data = read_device(handle, 64, timeout_ms=5000)
                        if data:
                            hex_str = " ".join(f"{b:02X}" for b in data)
                            if data != last:
                                marker = "  <-- CHANGE"
                                last = list(data)
                            else:
                                marker = ""
                            print(f"RECV [{len(data):2d}]: {hex_str}{marker}")
                        else:
                            print(".", end="", flush=True)
                except KeyboardInterrupt:
                    print("\n[INFO] Interrupted by user.")
                
                kernel32.CloseHandle(handle)
                return True
        else:
            print(f"  [WARN] Write failed.")
    
    print("[NG ] No response from this path. Closing.")
    kernel32.CloseHandle(handle)
    return False


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Post-Zadig Direct Path Test")
    print("=" * 80)

    # Device paths discovered from registry after Zadig replacement
    # These paths are known to exist but may have different access requirements
    
    paths_to_try = [
        # Original HID path (may now be inaccessible)
        (
            r"\\?\hid#vid_057e&pid_2069&mi_00#9&2ff21532&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}",
            "Original HID Interface (MI_00)"
        ),
        
        # WinUSB paths discovered from registry
        (
            r"\\?\usb#vid_057e&pid_2069#00#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
            "USB Device Path (Whole device)"
        ),
        
        # Vendor-specific interface paths (these are likely the WinUSB ones)
        (
            r"\\?\usb#vid_057e&pid_2069&mi_00#8&2356d3fd&0&0000#{a8382f75-98f9-4fc3-8af0-cdf0a37be89e}",
            "Vendor Interface 0 (MI_00) - WinUSB"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_01#8&2356d3fd&0&0001#{6f13725e-ef0e-4fd3-ae5f-b2de989ec825}",
            "Vendor Interface 1 (MI_01) - WinUSB"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_00#8&2356d3fd&0&0000#{dee824ef-729b-4a0e-9c14-b7117d33a817}",
            "Vendor Interface 0 (MI_00) - Alternative GUID"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_01#8&2356d3fd&0&0001#{dee824ef-729b-4a0e-9c14-b7117d33a817}",
            "Vendor Interface 1 (MI_01) - Alternative GUID"
        ),
    ]
    
    print(f"\n[INFO] Will try {len(paths_to_try)} path(s)...\n")
    
    for path, label in paths_to_try:
        if test_path(path, label):
            print("\n[SUCCESS] Initialization successful!")
            return
    
    print("\n[FATAL] Could not initialize any interface.")
    print("\nNext steps:")
    print("  A. Try running as Administrator.")
    print("  B. Check Device Manager for exact current device paths.")
    print("  C. Unplug and reconnect the USB cable, then try again.")
    print("  D. In Zadig, verify both Interface 0 and Interface 1 are WinUSB.")
    sys.exit(1)


if __name__ == "__main__":
    main()
