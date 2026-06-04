import sys
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Diagnostic: Read HID Report Descriptor Caps (sizes) for Switch 2 Pro
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

class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]

# Setup function prototypes
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

hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

hid.HidD_FreePreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]

hid.HidP_GetCaps = ctypes.windll.hid.HidP_GetCaps
hid.HidP_GetCaps.restype = wintypes.LONG
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]

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
                    # Get report caps
                    preparsed_data = ctypes.c_void_p()
                    if hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed_data)):
                        caps = HIDP_CAPS()
                        status = hid.HidP_GetCaps(preparsed_data, ctypes.byref(caps))
                        if status == 0:
                            print(f"\n[CAPS] Input Report Byte Length:  {caps.InputReportByteLength}")
                            print(f"[CAPS] Output Report Byte Length: {caps.OutputReportByteLength}")
                            print(f"[CAPS] Feature Report Byte Length: {caps.FeatureReportByteLength}")
                        else:
                            print(f"\n[WARN] HidP_GetCaps failed with status: {status:#010x}")
                        hid.HidD_FreePreparsedData(preparsed_data)
                    else:
                        print("\n[WARN] HidD_GetPreparsedData failed")
            kernel32.CloseHandle(handle)
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return path


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  Report Caps Diagnostic")
    print("=" * 80)

    path = get_target_path()
    if not path:
        print("\n[FATAL] Target device not found.")
        sys.exit(1)

    print(f"\n[INFO] Target path: {path}")
    print("\n[RESULT] Use the report sizes above to adjust initialization packets.")
    print("         If OutputReportByteLength is non-zero, pad all writes to that size.")
    print("         If FeatureReportByteLength is non-zero, use HidD_SetFeature instead of WriteFile.")


if __name__ == "__main__":
    main()
