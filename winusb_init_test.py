import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Wired Init & Raw HID Sniffer  --  WinUSB variant
# ---------------------------------------------------------------------------
#  This version enumerates USB devices (not HID) to find the controller
#  after it has been converted to WinUSB via Zadig.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32
setupapi = ctypes.windll.setupapi

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]

class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", wintypes.WCHAR * 1),
    ]

# USB Device GUID (for WinUSB/libusb devices)
GUID_DEVINTERFACE_USB_DEVICE = GUID(
    0xA5DCBF10, 0x6530, 0x11D2,
    (0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED)
)

TARGET_VID = "VID_057E"
TARGET_PID = "PID_2069"

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
MAX_PATH_LEN = 4096
ALLOC_SIZE = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + MAX_PATH_LEN
DETAIL_BUF_TYPE = ctypes.c_ubyte * ALLOC_SIZE


def get_target_usb_path():
    """Enumerate USB devices and find the one matching VID/PID."""
    hDevInfo = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(GUID_DEVINTERFACE_USB_DEVICE), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if hDevInfo == ctypes.c_void_p(-1).value:
        return None

    path = None
    index = 0
    base_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)

    while True:
        dev_iface_data = SP_DEVICE_INTERFACE_DATA()
        dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(
            hDevInfo, None, ctypes.byref(GUID_DEVINTERFACE_USB_DEVICE), index, ctypes.byref(dev_iface_data)
        ):
            break

        req_size = wintypes.DWORD(0)
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(
            hDevInfo, ctypes.byref(dev_iface_data), None, 0, ctypes.byref(req_size), None
        )
        err = kernel32.GetLastError()
        if ret != 0 or err != 122:
            index += 1
            continue
        if req_size.value > ALLOC_SIZE:
            index += 1
            continue

        buf = DETAIL_BUF_TYPE()
        ctypes.c_uint32.from_buffer(buf, 0).value = base_size
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(
            hDevInfo, ctypes.byref(dev_iface_data), ctypes.addressof(buf), req_size, None, None
        )
        if not ret:
            index += 1
            continue

        candidate = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        # Check if path contains target VID/PID
        if TARGET_VID in candidate.upper() and TARGET_PID in candidate.upper():
            path = candidate
            print(f"[INFO] Found USB device: {path}")
            break
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return path


def open_usb_device(path):
    """Open WinUSB device."""
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
        0x00000001 | 0x00000002,    # FILE_SHARE_READ | FILE_SHARE_WRITE
        None,
        3,                          # OPEN_EXISTING
        0,                          # No overlap for now
        None
    )
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def write_device(handle, data, report_size=64):
    """Write raw bytes to device, padded to report_size."""
    if len(data) < report_size:
        data = data + [0] * (report_size - len(data))
    elif len(data) > report_size:
        data = data[:report_size]
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = wintypes.DWORD(0)
    ret = kernel32.WriteFile(handle, buf, len(data), ctypes.byref(written), None)
    err = kernel32.GetLastError()
    if not ret:
        print(f"  [WARN] WriteFile failed. Error: {err}")
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


def attempt_initialization(handle) -> tuple[bool, bytes | None]:
    """Send known init sequences and look for a reply."""
    candidates = [
        ("Handshake 0x80 0x01 (padded 64 bytes)", [0x80, 0x01] + [0x00] * 62),
        ("Handshake 0x80 0x02 (padded 64 bytes)", [0x80, 0x02] + [0x00] * 62),
        ("64-byte zeros", [0x00] * 64),
    ]

    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_device(handle, payload):
            time.sleep(0.25)
            peek = read_device(handle, 64, timeout_ms=300)
            if peek:
                print(f"  [INIT] Controller responded ({len(peek)} bytes).")
                return True, peek
        else:
            print(f"  [WARN] Write failed.")

    # Set Report Mode (subcommand 0x03)
    for mode, label in ((0x3F, "Simple"), (0x30, "Standard Full")):
        print(f"  [INIT] Trying: Set Report Mode ({label}, 0x{mode:02X})")
        pkt = bytearray(64)
        pkt[0] = 0x01
        pkt[1] = 0x00
        pkt[10] = 0x03
        pkt[11] = mode
        if write_device(handle, list(pkt)):
            time.sleep(0.4)
            peek = read_device(handle, 64, timeout_ms=500)
            if peek:
                print(f"  [INIT] Controller responded ({len(peek)} bytes).")
                return True, peek
        else:
            print(f"  [WARN] Write failed.")

    return False, None


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  WinUSB Init & Raw Data Sniffer")
    print(" VID: 0x057E  |  PID: 0x2069")
    print("=" * 80)

    path = get_target_usb_path()
    if not path:
        print("\n[FATAL] Target USB device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Did you replace the driver with WinUSB using Zadig?")
        print("  3. Try unplugging and reconnecting the USB cable.")
        print("  4. Run this script as Administrator.")
        sys.exit(1)

    print(f"\n[TRY] Opening: {path}")
    handle = open_usb_device(path)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[FATAL] CreateFile failed. Error: {err}")
        sys.exit(1)

    print(f"[OK ] Handle opened: {handle}")
    print("[INFO] Attempting initialization...")
    ok, reply = attempt_initialization(handle)

    if not ok:
        print("\n[FATAL] Could not initialize device.")
        print("\nNext steps:")
        print("  A. Verify the controller is powered on.")
        print("  B. Try different init bytes in the script.")
        print("  C. Check if another app is holding the device.")
        kernel32.CloseHandle(handle)
        sys.exit(1)

    print(f"\n[INFO] Initialization succeeded!")
    print("=" * 80)
    print("[READ] Entering main read loop.  Press Ctrl+C to stop.")
    print("=" * 80)

    last = None
    if reply:
        hex_str = " ".join(f"{b:02X}" for b in reply)
        print(f"RECV [{len(reply):2d}]: {hex_str}  <-- INIT-REPLY")
        last = list(reply)

    try:
        while True:
            data = read_device(handle, 64, timeout_ms=5000)
            if data:
                hex_str = " ".join(f"{b:02X}" for b in data)
                if data != last:
                    marker = "  <-- CHANGE"
                    stable_cnt = 0
                    last = list(data)
                else:
                    stable_cnt += 1
                    marker = " (stable)" if stable_cnt == 1 else ""
                print(f"RECV [{len(data):2d}]: {hex_str}{marker}")
            else:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    print("\n[INFO] Closing device.")
    kernel32.CloseHandle(handle)
    print("Done.")


if __name__ == "__main__":
    main()
