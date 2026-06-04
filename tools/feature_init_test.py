import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  Wired Init Test  --  Feature Report variant
# ---------------------------------------------------------------------------
#  Uses HidD_SetFeature instead of WriteFile.
#  Some controllers require Feature Reports for initialization commands.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32
setupapi = ctypes.windll.setupapi
hid = ctypes.windll.hid

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

class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]

setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

hid.HidD_SetFeature.restype = wintypes.BOOL
hid.HidD_SetFeature.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.ULONG]

TARGET_VID = 0x057E
TARGET_PID = 0x2069
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
MAX_PATH_LEN = 4096
ALLOC_SIZE = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + MAX_PATH_LEN
DETAIL_BUF_TYPE = ctypes.c_ubyte * ALLOC_SIZE


def get_target_path():
    HidGuid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(HidGuid))
    hDevInfo = setupapi.SetupDiGetClassDevsW(ctypes.byref(HidGuid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hDevInfo == ctypes.c_void_p(-1).value:
        return None

    path = None
    index = 0
    base_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)

    while True:
        dev_iface_data = SP_DEVICE_INTERFACE_DATA()
        dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(hDevInfo, None, ctypes.byref(HidGuid), index, ctypes.byref(dev_iface_data)):
            break

        req_size = wintypes.DWORD(0)
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(hDevInfo, ctypes.byref(dev_iface_data), None, 0, ctypes.byref(req_size), None)
        err = kernel32.GetLastError()
        if ret != 0 or err != 122:
            index += 1
            continue
        if req_size.value > ALLOC_SIZE:
            index += 1
            continue

        buf = DETAIL_BUF_TYPE()
        ctypes.c_uint32.from_buffer(buf, 0).value = base_size
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(hDevInfo, ctypes.byref(dev_iface_data), ctypes.addressof(buf), req_size, None, None)
        if not ret:
            index += 1
            continue

        candidate = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        handle = kernel32.CreateFileW(candidate, 0, 0x00000001 | 0x00000002, None, 3, 0, None)
        if handle != ctypes.c_void_p(-1).value:
            attr = HIDD_ATTRIBUTES()
            attr.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
            if hid.HidD_GetAttributes(handle, ctypes.byref(attr)):
                if attr.VendorID == TARGET_VID and attr.ProductID == TARGET_PID:
                    path = candidate
            kernel32.CloseHandle(handle)
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return path


def send_feature_report(handle, data):
    """Send a Feature Report using HidD_SetFeature."""
    buf = (ctypes.c_ubyte * len(data))(*data)
    ret = hid.HidD_SetFeature(handle, ctypes.byref(buf), len(data))
    err = kernel32.GetLastError()
    if not ret:
        print(f"  [WARN] HidD_SetFeature failed. Error: {err}")
    else:
        print(f"  [OK ] HidD_SetFeature succeeded ({len(data)} bytes)")
    return ret


def read_device(handle, size, timeout_ms=5000):
    """Read raw bytes from HID device."""
    buf = (ctypes.c_ubyte * size)()
    read_count = wintypes.DWORD(0)
    ret = kernel32.ReadFile(handle, buf, size, ctypes.byref(read_count), None)
    if ret:
        return bytes(buf[:read_count.value])
    return None


def attempt_feature_init(handle):
    """Try initialization via Feature Reports."""
    print("\n[INIT] Trying Feature Report: Handshake 0x80 0x01 (padded 64 bytes)")
    if send_feature_report(handle, [0x80, 0x01] + [0x00] * 62):
        time.sleep(0.25)
        peek = read_device(handle, 64, timeout_ms=300)
        if peek:
            print(f"  [INIT] Controller responded immediately ({len(peek)} bytes).")
            return True, peek

    print("[INIT] Trying Feature Report: Set Report Mode 0x3F (padded 64 bytes)")
    pkt = bytearray(64)
    pkt[0] = 0x01
    pkt[1] = 0x00
    pkt[10] = 0x03
    pkt[11] = 0x3F
    if send_feature_report(handle, list(pkt)):
        time.sleep(0.4)
        peek = read_device(handle, 64, timeout_ms=500)
        if peek:
            print(f"  [INIT] Controller responded ({len(peek)} bytes).")
            return True, peek

    print("[INIT] Trying Feature Report: Set Report Mode 0x30 (padded 64 bytes)")
    pkt = bytearray(64)
    pkt[0] = 0x01
    pkt[1] = 0x00
    pkt[10] = 0x03
    pkt[11] = 0x30
    if send_feature_report(handle, list(pkt)):
        time.sleep(0.4)
        peek = read_device(handle, 64, timeout_ms=500)
        if peek:
            print(f"  [INIT] Controller responded ({len(peek)} bytes).")
            return True, peek

    return False, None


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Feature Report Init Test")
    print("=" * 80)

    path = get_target_path()
    if not path:
        print("\n[FATAL] Target device not found.")
        sys.exit(1)

    print(f"\n[INFO] Target path: {path}")
    print("[TEST] Opening with GENERIC_WRITE...")

    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle == ctypes.c_void_p(-1).value:
        err = kernel32.GetLastError()
        print(f"[FATAL] CreateFile failed. Error: {err}")
        sys.exit(1)

    print(f"[OK ] Handle opened: {handle}")
    ok, reply = attempt_feature_init(handle)

    if not ok:
        print("\n[FATAL] Feature Report initialization failed.")
        print("\nNext steps:")
        print("  A. The device may not support Feature Reports for init.")
        print("  B. Try Zadig to replace the HID driver with WinUSB.")
        print("     https://zadig.akeo.ie")
        kernel32.CloseHandle(handle)
        sys.exit(1)

    print("\n" + "=" * 80)
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
    print("Done.")


if __name__ == "__main__":
    main()
