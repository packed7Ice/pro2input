import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Universal Device Finder  --  Enumerates ALL interfaces regardless of class
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

TARGET_VID = "VID_057E"
TARGET_PID = "PID_2069"

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
DIGCF_ALLCLASSES = 0x00000004
MAX_PATH_LEN = 4096
ALLOC_SIZE = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + MAX_PATH_LEN
DETAIL_BUF_TYPE = ctypes.c_ubyte * ALLOC_SIZE


def find_device_by_path_keyword(keyword):
    """Enumerate all present device interfaces and search by path substring."""
    # Pass NULL as the GUID to enumerate all device interfaces
    hDevInfo = setupapi.SetupDiGetClassDevsW(
        None, None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE | DIGCF_ALLCLASSES
    )
    if hDevInfo == ctypes.c_void_p(-1).value:
        err = kernel32.GetLastError()
        print(f"[FATAL] SetupDiGetClassDevsW failed. Error: {err}")
        return []

    results = []
    index = 0
    base_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)

    while True:
        dev_iface_data = SP_DEVICE_INTERFACE_DATA()
        dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(
            hDevInfo, None, None, index, ctypes.byref(dev_iface_data)
        ):
            err = kernel32.GetLastError()
            if err == 259:  # ERROR_NO_MORE_ITEMS
                break
            else:
                print(f"[WARN] SetupDiEnumDeviceInterfaces failed. Error: {err}")
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

        path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        if keyword.upper() in path.upper():
            results.append(path)
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return results


def open_device(path):
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def write_device(handle, data, report_size=64):
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
    buf = (ctypes.c_ubyte * size)()
    read_count = wintypes.DWORD(0)
    ret = kernel32.ReadFile(handle, buf, size, ctypes.byref(read_count), None)
    if ret:
        return bytes(buf[:read_count.value])
    return None


def main():
    print("=" * 80)
    print(" Universal Device Finder  --  Switch 2 Pro Controller")
    print("=" * 80)

    print(f"\n[INFO] Searching for '{TARGET_VID}&{TARGET_PID}' in all device interfaces...")
    paths = find_device_by_path_keyword(f"{TARGET_VID}&{TARGET_PID}")

    if not paths:
        print("\n[FATAL] No device path found containing VID_057E&PID_2069.")
        print("\nPossible reasons:")
        print("  1. Controller is not connected via USB.")
        print("  2. Zadig replacement was not applied correctly.")
        print("  3. Need to run as Administrator.")
        sys.exit(1)

    print(f"\n[INFO] Found {len(paths)} path(s):")
    for i, p in enumerate(paths):
        print(f"  [{i}] {p}")

    # Try each path
    for path in paths:
        print(f"\n[TRY] Opening: {path}")
        handle = open_device(path)
        if not handle:
            err = kernel32.GetLastError()
            print(f"[NG ] CreateFile failed. Error: {err}")
            continue

        print(f"[OK ] Handle opened: {handle}")

        # Try init sequences
        init_candidates = [
            ("64-byte zeros", [0x00] * 64),
            ("Handshake 0x80 0x01 (padded)", [0x80, 0x01] + [0x00] * 62),
            ("Set Report Mode 0x3F", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x3F] + [0x00] * 52),
            ("Set Report Mode 0x30", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x30] + [0x00] * 52),
        ]

        ok = False
        for name, payload in init_candidates:
            print(f"  [INIT] Trying: {name}")
            if write_device(handle, payload):
                time.sleep(0.3)
                peek = read_device(handle, 64, timeout_ms=500)
                if peek:
                    print(f"  [OK ] Controller responded ({len(peek)} bytes).")
                    ok = True
                    break
            else:
                print(f"  [WARN] Write failed.")

        if not ok:
            print("[NG ] No response from this path. Closing.")
            kernel32.CloseHandle(handle)
            continue

        print("\n" + "=" * 80)
        print("[READ] Entering main read loop.  Press Ctrl+C to stop.")
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

        print("\n[INFO] Closing device.")
        kernel32.CloseHandle(handle)
        return

    print("\n[FATAL] Could not initialize any interface.")
    sys.exit(1)


if __name__ == "__main__":
    main()
