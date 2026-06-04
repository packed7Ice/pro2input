import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  libusbK Direct Path Test
# ---------------------------------------------------------------------------
#  Uses discovered registry paths for post-Zadig libusbK devices.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32

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

# libusbK function prototypes
libusbK.UsbK_Init.restype = wintypes.BOOL
libusbK.UsbK_Init.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

libusbK.UsbK_Free.restype = wintypes.BOOL
libusbK.UsbK_Free.argtypes = [ctypes.c_void_p]

libusbK.UsbK_WritePipe.restype = wintypes.BOOL
libusbK.UsbK_WritePipe.argtypes = [
    ctypes.c_void_p, wintypes.BYTE, ctypes.c_void_p,
    wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.c_void_p
]

libusbK.UsbK_ReadPipe.restype = wintypes.BOOL
libusbK.UsbK_ReadPipe.argtypes = [
    ctypes.c_void_p, wintypes.BYTE, ctypes.c_void_p,
    wintypes.UINT, ctypes.POINTER(wintypes.UINT), ctypes.c_void_p
]


def open_device(path):
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


def test_path(path, label):
    """Try to open a path and initialize the controller via libusbK."""
    print(f"\n[TRY] {label}")
    print(f"      Path: {path}")

    handle = open_device(path)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[NG ] CreateFile failed. Error: {err}")
        return False

    print(f"[OK ] Handle opened: {handle}")

    # Initialize libusbK
    usb_handle = ctypes.c_void_p()
    if not libusbK.UsbK_Init(handle, ctypes.byref(usb_handle)):
        err = kernel32.GetLastError()
        print(f"[NG ] UsbK_Init failed. Error: {err}")
        kernel32.CloseHandle(handle)
        return False

    print(f"[OK ] libusbK initialized. USB handle: {usb_handle.value}")

    # Try various init sequences
    pipe_id_out = 0x01
    pipe_id_in = 0x81

    candidates = [
        ("64-byte zeros", [0x00] * 64),
        ("Handshake 0x80 0x01", [0x80, 0x01] + [0x00] * 62),
        ("Handshake 0x80 0x02", [0x80, 0x02] + [0x00] * 62),
        ("Report Mode 0x3F", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x3F] + [0x00] * 52),
        ("Report Mode 0x30", [0x01, 0x00] + [0x00] * 8 + [0x03, 0x30] + [0x00] * 52),
    ]

    ok = False
    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_pipe(usb_handle, pipe_id_out, payload):
            time.sleep(0.3)
            peek = read_pipe(usb_handle, pipe_id_in, 64, timeout_ms=500)
            if peek:
                print(f"  [OK ] Controller responded ({len(peek)} bytes)!")
                ok = True
                break
        else:
            print(f"  [WARN] Write failed.")

    if not ok:
        print("[NG ] No response from this path. Closing.")
        libusbK.UsbK_Free(usb_handle)
        kernel32.CloseHandle(handle)
        return False

    print("\n" + "=" * 80)
    print("[READ] Entering main read loop. Press Ctrl+C to stop.")
    print("=" * 80)

    last = None
    try:
        while True:
            data = read_pipe(usb_handle, pipe_id_in, 64, timeout_ms=5000)
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
    libusbK.UsbK_Free(usb_handle)
    kernel32.CloseHandle(handle)
    return True


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  libusbK Direct Path Test")
    print("=" * 80)

    # Device paths discovered from registry after Zadig libusbK replacement
    paths_to_try = [
        (
            r"\\?\usb#vid_057e&pid_2069&mi_01#8&2356d3fd&0&0001#{6f13725e-ef0e-4fd3-ae5f-b2de989ec825}",
            "Vendor Interface 1 (MI_01) - libusbK"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_00#8&2356d3fd&0&0000#{a8382f75-98f9-4fc3-8af0-cdf0a37be89e}",
            "Vendor Interface 0 (MI_00) - libusbK"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_01#8&2356d3fd&0&0001#{dee824ef-729b-4a0e-9c14-b7117d33a817}",
            "Vendor Interface 1 (MI_01) - Alternative GUID"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069&mi_00#8&2356d3fd&0&0000#{dee824ef-729b-4a0e-9c14-b7117d33a817}",
            "Vendor Interface 0 (MI_00) - Alternative GUID"
        ),
        (
            r"\\?\usb#vid_057e&pid_2069#00#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
            "USB Device Path (Whole device)"
        ),
    ]

    print(f"\n[INFO] Will try {len(paths_to_try)} path(s)...\n")

    for path, label in paths_to_try:
        if test_path(path, label):
            print("\n[SUCCESS] Initialization successful!")
            return

    print("\n[FATAL] Could not initialize any interface.")
    print("\nNext steps:")
    print("  A. Verify Zadig was applied to the correct interface.")
    print("  B. Check if the device path has changed after driver replacement.")
    print("  C. Try unplugging and reconnecting the USB cable.")
    print("  D. Run Device Manager to check the exact current device path.")
    sys.exit(1)


if __name__ == "__main__":
    main()
