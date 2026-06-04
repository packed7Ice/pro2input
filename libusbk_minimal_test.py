import sys
import time
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Minimal libusbK test for Switch 2 Pro Controller
#  Tests different UsbK_Init signatures to find the correct one.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32

# Load libusbK
try:
    libusbK = ctypes.windll.libusbK
except OSError:
    print("[FATAL] libusbK.dll not found.")
    sys.exit(1)

# Device path (the one that CreateFile succeeded for)
DEVICE_PATH = r"\\?\usb#vid_057e&pid_2069#00#{a5dcbf10-6530-11d2-901f-00c04fb951ed}"


def open_device(path):
    handle = kernel32.CreateFileW(
        path,
        0x80000000 | 0x40000000,
        0x00000001 | 0x00000002,
        None, 3, 0, None
    )
    if handle == -1 or handle == 0:
        return None
    return handle


def main():
    print("=" * 80)
    print(" Minimal libusbK Init Test")
    print("=" * 80)

    handle = open_device(DEVICE_PATH)
    if not handle:
        err = kernel32.GetLastError()
        print(f"[FATAL] CreateFile failed. Error: {err}")
        sys.exit(1)

    print(f"[OK ] CreateFile handle: {handle}")

    # Try different UsbK_Init signatures
    # Signature 1: UsbK_Init(HANDLE, PKUSB_HANDLE)
    #   where PKUSB_HANDLE is void**
    print("\n[Test 1] UsbK_Init(handle, ctypes.byref(usb_handle))")
    usb_handle = ctypes.c_void_p()
    try:
        ret = libusbK.UsbK_Init(handle, ctypes.byref(usb_handle))
        if ret:
            print(f"[OK ] Success! usb_handle={usb_handle.value}")
        else:
            err = kernel32.GetLastError()
            print(f"[FAIL] Failed. Error: {err}")
    except Exception as e:
        print(f"[CRASH] {e}")

    # Signature 2: UsbK_Init(PKUSB_HANDLE, HANDLE)
    #   Swapped order
    print("\n[Test 2] UsbK_Init(ctypes.byref(usb_handle), handle)")
    usb_handle = ctypes.c_void_p()
    try:
        ret = libusbK.UsbK_Init(ctypes.byref(usb_handle), handle)
        if ret:
            print(f"[OK ] Success! usb_handle={usb_handle.value}")
        else:
            err = kernel32.GetLastError()
            print(f"[FAIL] Failed. Error: {err}")
    except Exception as e:
        print(f"[CRASH] {e}")

    # Signature 3: Try with a struct pointer
    print("\n[Test 3] UsbK_Init(handle, ctypes.byref(struct_ptr))")
    class KUSB_STRUCT(ctypes.Structure):
        _fields_ = [("dummy", ctypes.c_byte * 64)]
    
    struct_ptr = KUSB_STRUCT()
    try:
        ret = libusbK.UsbK_Init(handle, ctypes.byref(struct_ptr))
        if ret:
            print(f"[OK ] Success! struct at {ctypes.addressof(struct_ptr)}")
        else:
            err = kernel32.GetLastError()
            print(f"[FAIL] Failed. Error: {err}")
    except Exception as e:
        print(f"[CRASH] {e}")

    # Signature 4: Try with pointer to struct as first arg
    print("\n[Test 4] UsbK_Init(ctypes.byref(struct_ptr), handle)")
    struct_ptr = KUSB_STRUCT()
    try:
        ret = libusbK.UsbK_Init(ctypes.byref(struct_ptr), handle)
        if ret:
            print(f"[OK ] Success! struct at {ctypes.addressof(struct_ptr)}")
        else:
            err = kernel32.GetLastError()
            print(f"[FAIL] Failed. Error: {err}")
    except Exception as e:
        print(f"[CRASH] {e}")

    # Try with integer handle directly
    print("\n[Test 5] UsbK_Init(handle_value, ctypes.byref(usb_handle))")
    usb_handle = ctypes.c_void_p()
    try:
        ret = libusbK.UsbK_Init(ctypes.c_void_p(handle), ctypes.byref(usb_handle))
        if ret:
            print(f"[OK ] Success! usb_handle={usb_handle.value}")
        else:
            err = kernel32.GetLastError()
            print(f"[FAIL] Failed. Error: {err}")
    except Exception as e:
        print(f"[CRASH] {e}")

    print("\n[INFO] Closing device handle.")
    kernel32.CloseHandle(handle)
    print("Done.")


if __name__ == "__main__":
    main()
