import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Wired Init & Raw HID Sniffer  --  Pure Python / Windows API (ctypes)
# ---------------------------------------------------------------------------
#  NO external pip packages required.  Uses only the Python standard library.
#  Tested on Windows 10/11.
# ---------------------------------------------------------------------------

# --- Windows API type definitions ---

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000

# HID GUID
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

HidGuid = GUID()

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

class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]

# Load DLLs
setupapi = ctypes.windll.setupapi
kernel32 = ctypes.windll.kernel32
hid = ctypes.windll.hid

# Function prototypes
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD
]

setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)
]

setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
]

setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

# Pre-allocate buffer size for detail data
MAX_PATH_LEN = 4096
ALLOC_SIZE = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + MAX_PATH_LEN
DETAIL_BUF_TYPE = ctypes.c_ubyte * ALLOC_SIZE

# ---------------------------------------------------------------------------

def get_hid_device_paths(target_vid, target_pid):
    """Enumerate HID device paths that match VID/PID."""
    hid.HidD_GetHidGuid(ctypes.byref(HidGuid))

    hDevInfo = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(HidGuid), None, None, 0x00000010 | 0x00000002
    )
    if hDevInfo == INVALID_HANDLE_VALUE:
        return []

    paths = []
    index = 0
    base_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)

    while True:
        dev_iface_data = SP_DEVICE_INTERFACE_DATA()
        dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(
            hDevInfo, None, ctypes.byref(HidGuid), index, ctypes.byref(dev_iface_data)
        ):
            break

        # Get required size
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
            hDevInfo, ctypes.byref(dev_iface_data),
            ctypes.addressof(buf), req_size, None, None
        )
        if not ret:
            index += 1
            continue

        path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        # Open device to check VID/PID
        handle = kernel32.CreateFileW(
            path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
        )
        if handle != INVALID_HANDLE_VALUE:
            attr = HIDD_ATTRIBUTES()
            attr.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
            if hid.HidD_GetAttributes(handle, ctypes.byref(attr)):
                if attr.VendorID == target_vid and attr.ProductID == target_pid:
                    paths.append(path)
            kernel32.CloseHandle(handle)
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return paths


def open_hid_device(path):
    """Open HID device with read/write access."""
    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,  # FILE_FLAG_OVERLAPPED for async; 0 for sync
        None
    )
    if handle == INVALID_HANDLE_VALUE or not handle:
        return None
    return handle


def write_device(handle, data, report_size=64):
    """Write raw bytes to HID device, padded to report_size."""
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
    return ret != 0


def read_device(handle, size, timeout_ms=5000):
    """Read raw bytes from HID device."""
    buf = (ctypes.c_ubyte * size)()
    read_count = wintypes.DWORD(0)
    ret = kernel32.ReadFile(handle, buf, size, ctypes.byref(read_count), None)
    if ret:
        return bytes(buf[:read_count.value])
    return None


# ---------------------------------------------------------------------------
#  Initialization helpers
# ---------------------------------------------------------------------------

def attempt_initialization(handle) -> tuple[bool, bytes | None]:
    """Send known init sequences and look for a reply."""
    candidates = [
        ("Handshake 0x80 0x01 (raw 2-byte)", [0x80, 0x01]),
        ("Handshake 0x80 0x01 (with Report ID 0x00)", [0x00, 0x80, 0x01]),
        ("Handshake 0x80 0x01 (padded to 64 bytes)", [0x80, 0x01] + [0x00] * 62),
    ]

    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_device(handle, payload):
            time.sleep(0.25)
            peek = read_device(handle, 64, timeout_ms=300)
            if peek:
                print(f"  [INIT] Controller responded immediately ({len(peek)} bytes).")
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


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    TARGET_VID = 0x057E
    TARGET_PID = 0x2069

    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Wired Init & Raw HID Sniffer")
    print(" VID: 0x057E  |  PID: 0x2069")
    print(" (using ctypes + Windows API -- NO external packages)")
    print("=" * 80)

    print("\n[INFO] Enumerating HID interfaces...")
    paths = get_hid_device_paths(TARGET_VID, TARGET_PID)

    if not paths:
        print("\n[FATAL] No device found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. On Windows, does 'Device Manager' show the controller?")
        print("  3. If another app (Steam, BetterJoy, etc.) is running, close it.")
        print("  4. You may need to install the WinUSB/libusbK driver for the")
        print("     *vendor-specific* interface using Zadig (https://zadig.akeo.ie).")
        print("  5. Try running this script as Administrator.")
        sys.exit(1)

    print(f"\n[INFO] Found {len(paths)} interface(s).")
    for i, p in enumerate(paths):
        print(f"  [{i}] {p}")

    chosen_handle = None
    chosen_path = None
    init_reply = None

    for path in paths:
        print(f"\n[TRY] Opening: {path}")
        handle = open_hid_device(path)
        if not handle:
            print(f"[NG ] Failed to open handle (access denied or occupied).")
            continue

        print(f"[OK ] Opened. Attempting initialization...")
        ok, reply = attempt_initialization(handle)
        if ok:
            chosen_handle = handle
            chosen_path = path
            init_reply = reply
            print(f"[OK ] Initialization succeeded on this interface.")
            break
        else:
            print(f"[NG ] No response. Closing.")
            kernel32.CloseHandle(handle)

    if chosen_handle is None:
        print("\n[FATAL] Could not initialize any interface.")
        print("\nNext steps:")
        print("  A. Verify no other program is holding the device.")
        print("  B. Try replacing the handshake bytes (e.g. 0x80 0x02) in the script.")
        print("  C. Check Zadig/driver setup for the vendor interface.")
        print("  D. Run this script as Administrator.")
        sys.exit(1)

    print(f"\n[INFO] Using interface: {chosen_path}")
    print("       Starting live hex dump...  Press Ctrl+C to stop.\n")
    print("=" * 80)

    last = None
    stable_cnt = 0

    if init_reply:
        hex_str = " ".join(f"{b:02X}" for b in init_reply)
        print(f"RECV [{len(init_reply):2d}]: {hex_str}  <-- INIT-REPLY")
        last = list(init_reply)

    try:
        while True:
            data = read_device(chosen_handle, 64, timeout_ms=5000)
            if data:
                hex_str = " ".join(f"{b:02X}" for b in data)
                if data != last:
                    marker = "  <-- CHANGE"
                    stable_cnt = 0
                else:
                    stable_cnt += 1
                    marker = " (stable)" if stable_cnt == 1 else ""
                print(f"RECV [{len(data):2d}]: {hex_str}{marker}")
                last = list(data)
            else:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    print("\n[INFO] Closing device.")
    kernel32.CloseHandle(chosen_handle)
    print("Done.")


if __name__ == "__main__":
    main()
