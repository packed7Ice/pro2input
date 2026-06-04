import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  libusbK Init & Raw Data Sniffer
# ---------------------------------------------------------------------------
#  Requires libusbK driver installed via Zadig.
#  Uses libusbK.dll (UsbK_xxx API) for USB pipe I/O.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32
setupapi = ctypes.windll.setupapi

# Try to load libusbK.dll
try:
    libusbK = ctypes.windll.libusbK
except OSError:
    try:
        libusbK = ctypes.CDLL("C:\\Windows\\System32\\libusbK.dll")
    except OSError:
        print("[FATAL] libusbK.dll not found.")
        print("        Please install libusbK driver via Zadig first.")
        print("        https://zadig.akeo.ie")
        sys.exit(1)

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

# USB Device GUID (for WinUSB/libusbK devices)
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

# libusbK function prototypes
libusbK.UsbK_Init.restype = wintypes.BOOL
libusbK.UsbK_Init.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

libusbK.UsbK_Free.restype = wintypes.BOOL
libusbK.UsbK_Free.argtypes = [ctypes.c_void_p]

libusbK.UsbK_WritePipe.restype = wintypes.BOOL
libusbK.UsbK_WritePipe.argtypes = [
    ctypes.c_void_p, wintypes.UCHAR, ctypes.c_void_p,
    wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.c_void_p
]

libusbK.UsbK_ReadPipe.restype = wintypes.BOOL
libusbK.UsbK_ReadPipe.argtypes = [
    ctypes.c_void_p, wintypes.UCHAR, ctypes.c_void_p,
    wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.c_void_p
]


def get_usb_device_path():
    """Enumerate USB devices and find the one matching VID/PID."""
    hDevInfo = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(GUID_DEVINTERFACE_USB_DEVICE), None, None,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
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
            hDevInfo, None, ctypes.byref(GUID_DEVINTERFACE_USB_DEVICE),
            index, ctypes.byref(dev_iface_data)
        ):
            break

        req_size = wintypes.DWORD(0)
        ret = setupapi.SetupDiGetDeviceInterfaceDetailW(
            hDevInfo, ctypes.byref(dev_iface_data), None, 0,
            ctypes.byref(req_size), None
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
            hDevInfo, ctypes.byref(dev_iface_data), ctypes.addressof(buf),
            req_size, None, None
        )
        if not ret:
            index += 1
            continue

        candidate = ctypes.wstring_at(ctypes.addressof(buf) + 4)
        if TARGET_VID in candidate.upper() and TARGET_PID in candidate.upper():
            path = candidate
            break
        index += 1

    setupapi.SetupDiDestroyDeviceInfoList(hDevInfo)
    return path


def open_usb_device(path):
    """Open device with read/write access."""
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def write_pipe(usb_handle, pipe_id, data, report_size=64):
    """Write data via UsbK_WritePipe."""
    if len(data) < report_size:
        data = data + [0] * (report_size - len(data))
    elif len(data) > report_size:
        data = data[:report_size]
    buf = (ctypes.c_ubyte * len(data))(*data)
    transferred = wintypes.UINT(0)
    ret = libusbK.UsbK_WritePipe(
        usb_handle, pipe_id, ctypes.byref(buf), len(data),
        ctypes.byref(transferred), None
    )
    err = kernel32.GetLastError()
    if not ret:
        print(f"  [WARN] UsbK_WritePipe failed. Error: {err}")
        return False
    return True


def read_pipe(usb_handle, pipe_id, size, timeout_ms=5000):
    """Read data via UsbK_ReadPipe."""
    buf = (ctypes.c_ubyte * size)()
    transferred = wintypes.UINT(0)
    ret = libusbK.UsbK_ReadPipe(
        usb_handle, pipe_id, ctypes.byref(buf), size,
        ctypes.byref(transferred), None
    )
    if ret:
        return bytes(buf[:transferred.value])
    return None


def attempt_initialization(usb_handle) -> tuple[bool, bytes | None]:
    """Send known init sequences and look for a reply."""
    # Common interrupt OUT pipe for HID devices
    pipe_id_out = 0x01
    # Common interrupt IN pipe for HID devices
    pipe_id_in = 0x81

    candidates = [
        ("Handshake 0x80 0x01 (padded 64 bytes)", [0x80, 0x01] + [0x00] * 62),
        ("Handshake 0x80 0x02 (padded 64 bytes)", [0x80, 0x02] + [0x00] * 62),
        ("64-byte zeros", [0x00] * 64),
    ]

    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_pipe(usb_handle, pipe_id_out, payload):
            time.sleep(0.25)
            peek = read_pipe(usb_handle, pipe_id_in, 64, timeout_ms=300)
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
        if write_pipe(usb_handle, pipe_id_out, list(pkt)):
            time.sleep(0.4)
            peek = read_pipe(usb_handle, pipe_id_in, 64, timeout_ms=500)
            if peek:
                print(f"  [INIT] Controller responded ({len(peek)} bytes).")
                return True, peek
        else:
            print(f"  [WARN] Write failed.")

    return False, None


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  libusbK Init & Raw Data Sniffer")
    print(" VID: 0x057E  |  PID: 0x2069")
    print("=" * 80)

    path = get_usb_device_path()
    if not path:
        print("\n[FATAL] Target USB device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Did you replace the driver with libusbK using Zadig?")
        print("  3. Try unplugging and reconnecting the USB cable.")
        print("  4. Run this script as Administrator.")
        sys.exit(1)

    print(f"\n[INFO] Found device: {path}")
    print("[TEST] Opening with GENERIC_READ | GENERIC_WRITE...")

    handle = open_usb_device(path)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[FATAL] CreateFile failed. Error: {err}")
        sys.exit(1)

    print(f"[OK ] Handle opened: {handle}")

    # Initialize libusbK
    usb_handle = ctypes.c_void_p()
    if not libusbK.UsbK_Init(handle, ctypes.byref(usb_handle)):
        err = kernel32.GetLastError()
        print(f"[FATAL] UsbK_Init failed. Error: {err}")
        kernel32.CloseHandle(handle)
        sys.exit(1)

    print(f"[OK ] libusbK initialized. USB handle: {usb_handle.value}")
    print("[INFO] Attempting initialization...")
    ok, reply = attempt_initialization(usb_handle)

    if not ok:
        print("\n[FATAL] Could not initialize device.")
        print("\nNext steps:")
        print("  A. Verify the controller is powered on.")
        print("  B. Try different init bytes in the script.")
        print("  C. Check if Zadig was applied to the correct interface.")
        print("  D. Run this script as Administrator.")
        libusbK.UsbK_Free(usb_handle)
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

    pipe_id_in = 0x81
    try:
        while True:
            data = read_pipe(usb_handle, pipe_id_in, 64, timeout_ms=5000)
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
    libusbK.UsbK_Free(usb_handle)
    kernel32.CloseHandle(handle)
    print("Done.")


if __name__ == "__main__":
    main()
