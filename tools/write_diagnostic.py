import sys
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Diagnostic: Test Write operations on Switch 2 Pro Controller
#  Reports exact Windows error codes when WriteFile fails.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32
setupapi = ctypes.windll.setupapi
hid = ctypes.windll.hid

def get_last_error():
    return kernel32.GetLastError()

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


def test_write(handle, data, name):
    buf = (ctypes.c_ubyte * len(data))(*data)
    written = wintypes.DWORD(0)
    ret = kernel32.WriteFile(handle, buf, len(data), ctypes.byref(written), None)
    err = get_last_error()
    if ret:
        print(f"  [OK ] {name}: wrote {written.value} bytes")
    else:
        print(f"  [FAIL] {name}: WriteFile returned FALSE. Error: {err}")
    return ret != 0


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Write Diagnostic Tool")
    print("=" * 80)

    path = get_target_path()
    if not path:
        print("\n[FATAL] Target device not found.")
        sys.exit(1)

    print(f"\n[INFO] Target path: {path}")
    print("\n[TEST] Opening with GENERIC_WRITE...")

    # Attempt 1: Read + Write
    handle_rw = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
        0x00000001 | 0x00000002,    # FILE_SHARE_READ | FILE_SHARE_WRITE
        None, 3, 0, None
    )
    if handle_rw == ctypes.c_void_p(-1).value:
        err = get_last_error()
        print(f"[FAIL] CreateFile (RW) failed. Error: {err}")
    else:
        print(f"[OK ] Handle opened (RW): {handle_rw}")
        test_write(handle_rw, [0x80, 0x01], "Handshake 0x80 0x01 (2 bytes)")
        test_write(handle_rw, [0x00, 0x80, 0x01], "Handshake with Report ID 0x00")
        test_write(handle_rw, [0x80, 0x01] + [0x00]*62, "Handshake padded 64 bytes")
        test_write(handle_rw, list(bytearray(64)), "64-byte zeros")
        test_write(handle_rw, [0x01, 0x00] + [0x00]*8 + [0x03, 0x3F] + [0x00]*52, "Set Report Mode 0x3F")
        kernel32.CloseHandle(handle_rw)

    print("\n[TEST] Opening with GENERIC_WRITE only...")
    handle_w = kernel32.CreateFileW(
        path,
        0x40000000,  # GENERIC_WRITE only
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle_w == ctypes.c_void_p(-1).value:
        err = get_last_error()
        print(f"[FAIL] CreateFile (W only) failed. Error: {err}")
    else:
        print(f"[OK ] Handle opened (W only): {handle_w}")
        test_write(handle_w, [0x80, 0x01], "Handshake 0x80 0x01")
        kernel32.CloseHandle(handle_w)

    print("\n[TEST] Opening with 0 access (share only)...")
    handle_0 = kernel32.CreateFileW(
        path,
        0,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle_0 == ctypes.c_void_p(-1).value:
        err = get_last_error()
        print(f"[FAIL] CreateFile (0 access) failed. Error: {err}")
    else:
        print(f"[OK ] Handle opened (0 access): {handle_0}")
        test_write(handle_0, [0x80, 0x01], "Handshake 0x80 0x01")
        kernel32.CloseHandle(handle_0)

    print("\n" + "=" * 80)
    print(" Diagnosis:")
    print("=" * 80)
    print("""
If ALL writes failed with Error 5 (ERROR_ACCESS_DENIED):
    -> Windows HID driver has exclusive access to this device.
    -> You need to use Zadig to replace the driver with WinUSB.

If Error 31 (ERROR_GEN_FAILURE):
    -> The device does not support the output report format.
    -> Try sending Feature Report instead (HidD_SetFeature).

If Error 6 (ERROR_INVALID_HANDLE):
    -> Handle was closed or invalid permissions.

If Error 0 but WriteFile returned FALSE:
    -> Check written bytes count; device may accept data but reply differently.
    """)


if __name__ == "__main__":
    main()
