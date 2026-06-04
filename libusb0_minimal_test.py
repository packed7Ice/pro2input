import sys
import ctypes
from ctypes import wintypes

# ---------------------------------------------------------------------------
#  Minimal libusb0 test for Switch 2 Pro Controller
#  Uses libusb0.dll (libusb-win32 API) directly.
# ---------------------------------------------------------------------------

kernel32 = ctypes.windll.kernel32

# Load libusb0
try:
    libusb0 = ctypes.windll.libusb0
    print("[INFO] Loaded libusb0.dll via WinDLL (stdcall)")
except OSError:
    try:
        libusb0 = ctypes.CDLL("libusb0.dll")
        print("[INFO] Loaded libusb0.dll via CDLL (cdecl)")
    except OSError:
        print("[FATAL] libusb0.dll not found.")
        sys.exit(1)

# Define usb_device_descriptor struct
class USB_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("bLength", wintypes.BYTE),
        ("bDescriptorType", wintypes.BYTE),
        ("bcdUSB", wintypes.USHORT),
        ("bDeviceClass", wintypes.BYTE),
        ("bDeviceSubClass", wintypes.BYTE),
        ("bDeviceProtocol", wintypes.BYTE),
        ("bMaxPacketSize0", wintypes.BYTE),
        ("idVendor", wintypes.USHORT),
        ("idProduct", wintypes.USHORT),
        ("bcdDevice", wintypes.USHORT),
        ("iManufacturer", wintypes.BYTE),
        ("iProduct", wintypes.BYTE),
        ("iSerialNumber", wintypes.BYTE),
        ("bNumConfigurations", wintypes.BYTE),
    ]

# Define usb_device struct
class USB_DEVICE(ctypes.Structure):
    pass

USB_DEVICE._fields_ = [
    ("next", ctypes.POINTER(USB_DEVICE)),
    ("prev", ctypes.POINTER(USB_DEVICE)),
    ("filename", ctypes.c_char * 256),
    ("bus", ctypes.c_void_p),  # struct usb_bus*
    ("descriptor", USB_DEVICE_DESCRIPTOR),
    ("config", ctypes.c_void_p),
    ("dev", ctypes.c_void_p),
    ("devnum", ctypes.c_ubyte),
    ("num_children", ctypes.c_ubyte),
    ("children", ctypes.c_void_p),
]

# Set up function prototypes
libusb0.usb_find_busses.restype = ctypes.c_int
libusb0.usb_find_busses.argtypes = []

libusb0.usb_find_devices.restype = ctypes.c_int
libusb0.usb_find_devices.argtypes = []

libusb0.usb_get_busses.restype = ctypes.c_void_p
libusb0.usb_get_busses.argtypes = []

libusb0.usb_open.restype = ctypes.c_void_p
libusb0.usb_open.argtypes = [ctypes.POINTER(USB_DEVICE)]

libusb0.usb_close.restype = ctypes.c_int
libusb0.usb_close.argtypes = [ctypes.c_void_p]

libusb0.usb_claim_interface.restype = ctypes.c_int
libusb0.usb_claim_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]

libusb0.usb_release_interface.restype = ctypes.c_int
libusb0.usb_release_interface.argtypes = [ctypes.c_void_p, ctypes.c_int]

libusb0.usb_set_configuration.restype = ctypes.c_int
libusb0.usb_set_configuration.argtypes = [ctypes.c_void_p, ctypes.c_int]

libusb0.usb_interrupt_write.restype = ctypes.c_int
libusb0.usb_interrupt_write.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]

libusb0.usb_interrupt_read.restype = ctypes.c_int
libusb0.usb_interrupt_read.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]

TARGET_VID = 0x057E
TARGET_PID = 0x2069


def find_device():
    """Find the Switch 2 Pro Controller via libusb0 enumeration."""
    print("\n[INFO] Finding USB busses...")
    ret = libusb0.usb_find_busses()
    print(f"[INFO] usb_find_busses returned: {ret}")

    print("[INFO] Finding USB devices...")
    ret = libusb0.usb_find_devices()
    print(f"[INFO] usb_find_devices returned: {ret}")

    print("[INFO] Getting busses...")
    busses = libusb0.usb_get_busses()
    if not busses:
        print("[WARN] No busses found.")
        return None

    print(f"[INFO] Bus list at: {busses}")

    # Iterate through busses and devices
    # The bus structure is a linked list
    bus = busses
    while bus:
        # Read bus struct (simplified, just need devices pointer)
        # bus structure: next, prev, dirname, devices, root_dev
        # devices is at offset 16 (next=8, prev=8, dirname=256, but let's use a different approach)
        
        # Actually, let's just read the devices pointer directly
        # We need to know the struct layout
        # struct usb_bus { struct usb_bus *next, *prev; char dirname[256]; struct usb_device *devices; struct usb_device *root_dev; }
        # next: 8 bytes, prev: 8 bytes, dirname: 256 bytes, devices: 8 bytes, root_dev: 8 bytes
        
        devices_ptr = ctypes.c_void_p.from_address(bus + 8 + 8 + 256).value
        if devices_ptr:
            dev = devices_ptr
            while dev:
                # Read the device struct
                device = USB_DEVICE.from_address(dev)
                vid = device.descriptor.idVendor
                pid = device.descriptor.idProduct
                print(f"[INFO] Found device: VID={vid:04X} PID={pid:04X}")
                
                if vid == TARGET_VID and pid == TARGET_PID:
                    print(f"[OK ] Target device found!")
                    return device
                
                # Move to next device
                dev = device.next
        
        # Move to next bus
        bus = ctypes.c_void_p.from_address(bus).value

    return None


def main():
    print("=" * 80)
    print(" Minimal libusb0 Test  --  Switch 2 Pro Controller")
    print("=" * 80)

    device = find_device()
    if not device:
        print("\n[FATAL] Target device not found.")
        sys.exit(1)

    print(f"\n[INFO] Opening device...")
    handle = libusb0.usb_open(ctypes.byref(device))
    if not handle:
        print("[FATAL] usb_open failed.")
        sys.exit(1)

    print(f"[OK ] Device opened. Handle: {handle}")

    # Try to set configuration and claim interface
    print("[INFO] Setting configuration...")
    ret = libusb0.usb_set_configuration(handle, 1)
    print(f"[INFO] usb_set_configuration returned: {ret}")

    print("[INFO] Claiming interface 0...")
    ret = libusb0.usb_claim_interface(handle, 0)
    print(f"[INFO] usb_claim_interface returned: {ret}")

    # Try to write
    print("[INFO] Trying to write 64-byte zeros...")
    data = bytes([0x00] * 64)
    ret = libusb0.usb_interrupt_write(handle, 0x01, data, len(data), 1000)
    print(f"[INFO] usb_interrupt_write returned: {ret}")

    if ret > 0:
        print(f"[OK ] Wrote {ret} bytes!")
        
        # Try to read
        print("[INFO] Trying to read...")
        read_buf = ctypes.create_string_buffer(64)
        ret = libusb0.usb_interrupt_read(handle, 0x81, read_buf, 64, 1000)
        print(f"[INFO] usb_interrupt_read returned: {ret}")
        if ret > 0:
            print(f"[OK ] Read {ret} bytes: {read_buf.raw[:ret].hex()}")
    else:
        print(f"[FAIL] Write failed with error: {ret}")

    print("\n[INFO] Releasing interface...")
    libusb0.usb_release_interface(handle, 0)
    
    print("[INFO] Closing device...")
    libusb0.usb_close(handle)
    print("Done.")


if __name__ == "__main__":
    main()
