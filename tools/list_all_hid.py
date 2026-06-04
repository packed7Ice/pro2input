import sys
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Diagnostic script v3: List ALL HID devices with robust error reporting
#  Uses fixed-size buffer allocation to avoid dynamic ctypes issues.
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

# Base structure with DevicePath[1] (ANYSIZE_ARRAY = 1)
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

# Setup function prototypes
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]

setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]

# We will cast buffer manually, so use c_void_p for flexibility
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, 
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), 
    ctypes.c_void_p,  # PSP_DEVICE_INTERFACE_DETAIL_DATA_W
    wintypes.DWORD, 
    ctypes.POINTER(wintypes.DWORD), 
    ctypes.c_void_p   # PSP_DEVINFO_DATA (optional)
]

setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.c_void_p]


TARGET_VID = 0x057E
TARGET_PID = 0x2069
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010


def main():
    print("=" * 80)
    print(" HID Device Enumeration Report (Diagnostic v3)")
    print("=" * 80)

    HidGuid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(HidGuid))
    print(f"[INFO] HID GUID: {HidGuid.Data1:08X}-{HidGuid.Data2:04X}-{HidGuid.Data3:04X}-" +
          f"{''.join(f'{b:02X}' for b in HidGuid.Data4)}")

    hDevInfo = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(HidGuid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if hDevInfo == ctypes.c_void_p(-1).value:
        err = get_last_error()
        print(f"[FATAL] SetupDiGetClassDevsW failed. Error: {err}")
        sys.exit(1)

    print(f"[INFO] Device Info List handle: {hDevInfo}")

    found_any = False
    index = 0
    
    # Pre-allocate a buffer big enough for any reasonable device path (4096 bytes)
    # This avoids dynamic allocation issues
    MAX_PATH_LEN = 4096
    alloc_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + MAX_PATH_LEN
    detail_buf_type = ctypes.c_ubyte * alloc_size
    
    while True:
        dev_iface_data = SP_DEVICE_INTERFACE_DATA()
        dev_iface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        
        if not setupapi.SetupDiEnumDeviceInterfaces(
            hDevInfo, None, ctypes.byref(HidGuid), index, ctypes.byref(dev_iface_data)
        ):
            err = get_last_error()
            if err == 259:  # ERROR_NO_MORE_ITEMS
                if index == 0:
                    print(f"[INFO] No HID interfaces found (ERROR_NO_MORE_ITEMS on first iteration).")
                break
            else:
                print(f"[WARN] SetupDiEnumDeviceInterfaces failed at index {index}. Error: {err}")
                break

        found_any = True

        # Get required size first
        req_size = wintypes.DWORD(0)
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(
            hDevInfo, ctypes.byref(dev_iface_data), None, 0, ctypes.byref(req_size), None
        )
        err = get_last_error()
        
        # First call should fail with ERROR_INSUFFICIENT_BUFFER (122)
        if ret != 0:
            print(f"[WARN] First call unexpectedly succeeded at index {index}.")
            index += 1
            continue
        if err != 122:
            print(f"[WARN] First call failed with unexpected error {err} at index {index}.")
            index += 1
            continue
        
        # Check if our pre-allocated buffer is big enough
        if req_size.value > alloc_size:
            print(f"[WARN] Required size ({req_size.value}) exceeds pre-allocated buffer ({alloc_size}). Skipping.")
            index += 1
            continue
        
        # Allocate and initialize buffer
        buf = detail_buf_type()
        # Set cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) which is 6 (DWORD + WCHAR[1])
        base_size = ctypes.sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)
        ctypes.c_uint32.from_buffer(buf, 0).value = base_size
        
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(
            hDevInfo, ctypes.byref(dev_iface_data), 
            ctypes.addressof(buf), 
            req_size, 
            None, 
            None
        )
        
        if not ret:
            err = get_last_error()
            print(f"[WARN] Second call failed at index {index}. Error: {err}")
            index += 1
            continue

        # Extract path: starts at offset 4 (after cbSize DWORD)
        path = ctypes.wstring_at(ctypes.addressof(buf) + 4)

        # Open handle to read VID/PID
        handle = kernel32.CreateFileW(
            path, 0, 0x00000001 | 0x00000002, None, 3, 0, None
        )
        vid = pid = ver = None
        if handle != ctypes.c_void_p(-1).value:
            attr = HIDD_ATTRIBUTES()
            attr.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
            if hid.HidD_GetAttributes(handle, ctypes.byref(attr)):
                vid = attr.VendorID
                pid = attr.ProductID
                ver = attr.VersionNumber
            kernel32.CloseHandle(handle)

        is_target = (vid == TARGET_VID and pid == TARGET_PID)
        marker = "  <<< TARGET" if is_target else ""
        print(f"\nDevice [{index}]{marker}")
        print(f"  Path       : {path}")
        print(f"  VID        : {f'{vid:04X}' if vid is not None else 'N/A'}")
        print(f"  PID        : {f'{pid:04X}' if pid is not None else 'N/A'}")
        print(f"  Version    : {f'{ver:04X}' if ver is not None else 'N/A'}")
        
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)

    print("\n" + "=" * 80)
    if not found_any:
        print("[RESULT] No HID interfaces enumerated.")
        print("\nPossible causes:")
        print("  1. No HID devices are connected.")
        print("  2. Windows HID service is not running.")
        print("  3. All HID devices are currently in use by other applications.")
        print("  4. There may be a driver-level issue preventing enumeration.")
        print("\nTroubleshooting steps:")
        print("  - Check Device Manager (devmgmt.msc) -> View -> Show hidden devices")
        print("  - Look for 'Nintendo' or 'HID-compliant game controller'")
        print("  - Try running this script as Administrator")
        print("  - Check if 'Human Interface Device Service' is running")
    else:
        print(f"[RESULT] Enumerated {index} HID interface(s).")
    print("=" * 80)


if __name__ == "__main__":
    main()
