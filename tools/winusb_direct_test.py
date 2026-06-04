import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Switch 2 Pro Controller (VID 0x057E / PID 0x2069)
#  WinUSB Direct Init & Raw Data Sniffer
# ---------------------------------------------------------------------------
#  Uses Windows native WinUSB API (winusb.dll) for direct USB I/O.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32

# Load WinUSB DLL
try:
    winusb = ctypes.windll.winusb
except OSError:
    print("[FATAL] winusb.dll not found. This is a standard Windows DLL.")
    print("        If missing, your Windows installation may be corrupted.")
    sys.exit(1)

# WinUSB API function prototypes
winusb.WinUsb_Initialize.restype = wintypes.BOOL
winusb.WinUsb_Initialize.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)
]

winusb.WinUsb_Free.restype = wintypes.BOOL
winusb.WinUsb_Free.argtypes = [ctypes.c_void_p]

winusb.WinUsb_WritePipe.restype = wintypes.BOOL
winusb.WinUsb_WritePipe.argtypes = [
    ctypes.c_void_p, wintypes.BYTE, ctypes.c_void_p,
    wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p
]

winusb.WinUsb_ReadPipe.restype = wintypes.BOOL
winusb.WinUsb_ReadPipe.argtypes = [
    ctypes.c_void_p, wintypes.BYTE, ctypes.c_void_p,
    wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p
]

# Device path (USB whole device, which CreateFile succeeded for)
DEVICE_PATH = r"\\?\usb#vid_057e&pid_2069#00#{a5dcbf10-6530-11d2-901f-00c04fb951ed}"

# Common pipe IDs for HID devices
PIPE_OUT = 0x01  # Interrupt OUT
PIPE_IN = 0x81   # Interrupt IN


def open_device(path):
    """Open device with read/write access."""
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
        0x00000001 | 0x00000002,    # FILE_SHARE_READ | FILE_SHARE_WRITE
        None,
        3,  # OPEN_EXISTING
        0,
        None
    )
    if handle == -1 or handle == 0:
        return None
    return handle


def write_pipe(winusb_handle, pipe_id, data, report_size=64):
    """Write data via WinUsb_WritePipe."""
    if len(data) < report_size:
        data = data + [0] * (report_size - len(data))
    elif len(data) > report_size:
        data = data[:report_size]
    buf = (ctypes.c_ubyte * len(data))(*data)
    transferred = wintypes.ULONG(0)
    ret = winusb.WinUsb_WritePipe(
        winusb_handle, pipe_id, ctypes.byref(buf), len(data),
        ctypes.byref(transferred), None
    )
    err = kernel32.GetLastError()
    if not ret:
        print(f"  [WARN] WinUsb_WritePipe failed. Error: {err}")
        return False
    return True


def read_pipe(winusb_handle, pipe_id, size, timeout_ms=5000):
    """Read data via WinUsb_ReadPipe."""
    buf = (ctypes.c_ubyte * size)()
    transferred = wintypes.ULONG(0)
    ret = winusb.WinUsb_ReadPipe(
        winusb_handle, pipe_id, ctypes.byref(buf), size,
        ctypes.byref(transferred), None
    )
    if ret:
        return bytes(buf[:transferred.value])
    return None


def attempt_initialization(winusb_handle) -> tuple[bool, bytes | None]:
    """Send known init sequences and look for a reply."""
    candidates = [
        ("64-byte zeros", [0x00] * 64),
        ("Handshake 0x80 0x01", [0x80, 0x01] + [0x00] * 62),
        ("Handshake 0x80 0x02", [0x80, 0x02] + [0x00] * 62),
    ]

    for name, payload in candidates:
        print(f"  [INIT] Trying: {name}")
        if write_pipe(winusb_handle, PIPE_OUT, payload):
            time.sleep(0.25)
            peek = read_pipe(winusb_handle, PIPE_IN, 64, timeout_ms=300)
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
        if write_pipe(winusb_handle, PIPE_OUT, list(pkt)):
            time.sleep(0.4)
            peek = read_pipe(winusb_handle, PIPE_IN, 64, timeout_ms=500)
            if peek:
                print(f"  [INIT] Controller responded ({len(peek)} bytes).")
                return True, peek
        else:
            print(f"  [WARN] Write failed.")

    return False, None


def main():
    print("=" * 80)
    print(" Switch 2 Pro Controller  --  WinUSB Direct Init & Raw Data Sniffer")
    print(" VID: 0x057E  |  PID: 0x2069")
    print("=" * 80)

    print(f"\n[INFO] Opening: {DEVICE_PATH}")
    handle = open_device(DEVICE_PATH)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[FATAL] CreateFile failed. Error: {err}")
        sys.exit(1)

    print(f"[OK ] Handle opened: {handle}")

    # Initialize WinUSB
    winusb_handle = ctypes.c_void_p()
    ret = winusb.WinUsb_Initialize(handle, ctypes.byref(winusb_handle))
    if not ret:
        err = kernel32.GetLastError()
        print(f"[FATAL] WinUsb_Initialize failed. Error: {err}")
        kernel32.CloseHandle(handle)
        sys.exit(1)

    print(f"[OK ] WinUSB initialized. Handle: {winusb_handle.value}")
    print("[INFO] Attempting initialization...")
    ok, reply = attempt_initialization(winusb_handle)

    if not ok:
        print("\n[FATAL] Could not initialize device.")
        print("\nNext steps:")
        print("  A. Verify the controller is powered on.")
        print("  B. Try different init bytes in the script.")
        print("  C. Check if Zadig was applied to the correct interface.")
        print("  D. Run this script as Administrator.")
        winusb.WinUsb_Free(winusb_handle)
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
            data = read_pipe(winusb_handle, PIPE_IN, 64, timeout_ms=5000)
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
    winusb.WinUsb_Free(winusb_handle)
    kernel32.CloseHandle(handle)
    print("Done.")


if __name__ == "__main__":
    main()
