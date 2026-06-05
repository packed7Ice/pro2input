"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller.
Uses a hybrid approach:
  - pyusb (libusb) for Interface 1 Bulk OUT (initialization commands)
  - pywinusb (Windows HID API) for Interface 0 HID (input reading + rumble output)

Interface 0 MUST be driven by HidUsb (Windows standard HID driver).
Interface 1 should have libusbK or WinUSB installed via Zadig.
"""

import time
import usb.core
import usb.util

from pywinusb.hid import HidDeviceFilter

from core.constants import TARGET_VID, TARGET_PID, USB_INTERFACE_NUMBER, INIT_COMMANDS


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        self.device: usb.core.Device | None = None
        self.cfg = None
        self.ep1_out = None  # Interface 1 Bulk OUT (init commands)
        self.ep1_in = None   # Interface 1 Bulk IN  (optional)
        self.hid_device = None  # pywinusb HidDevice (Interface 0)

    def find_and_connect(self) -> bool:
        """Find the controller and set USB configuration."""
        self.device = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
        if self.device is None:
            return False
        self.device.set_configuration()
        self.cfg = self.device.get_active_configuration()
        return True

    def initialize_hid_mode(self) -> bool:
        """
        1. Send init commands via Interface 1 (Bulk OUT) using pyusb.
        2. Open Interface 0 (HID) via pywinusb for input/output reports.
        """
        # ---- Interface 1: Bulk OUT init sequence ----
        intf1 = usb.util.find_descriptor(self.cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
        if intf1 is None:
            raise RuntimeError("Interface 1 not found")

        for ep in intf1:
            direction = usb.util.endpoint_direction(ep.bEndpointAddress)
            if direction == usb.util.ENDPOINT_OUT:
                self.ep1_out = ep.bEndpointAddress
            elif direction == usb.util.ENDPOINT_IN:
                self.ep1_in = ep.bEndpointAddress

        if self.ep1_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")

        try:
            usb.util.claim_interface(self.device, USB_INTERFACE_NUMBER)
        except usb.core.USBError:
            pass

        for cmd in INIT_COMMANDS:
            try:
                self.device.write(self.ep1_out, cmd)
            except usb.core.USBError:
                pass
            time.sleep(0.05)

        try:
            usb.util.release_interface(self.device, USB_INTERFACE_NUMBER)
        except Exception:
            pass

        # ---- Interface 0: HID open via pywinusb ----
        devices = HidDeviceFilter(vendor_id=TARGET_VID, product_id=TARGET_PID).get_devices()
        if not devices:
            raise RuntimeError(
                "HID device not found. "
                "Make sure Interface 0 uses HidUsb (Windows standard HID driver). "
                "If you installed WinUSB/libusbK on Interface 0 via Zadig, "
                "restore HidUsb in Device Manager."
            )

        self.hid_device = devices[0]
        self.hid_device.open()
        return True

    def read_input(self, timeout: int = 100) -> list | None:
        """Read an input report from Interface 0 via pywinusb."""
        if self.hid_device is None:
            return None
        try:
            # pywinusb read returns a list of bytes
            data = self.hid_device.read(64)
            if data:
                return list(data)[1:]  # Skip Report ID
        except Exception:
            return None
        return None

    def write_output_report(self, report: bytes) -> bool:
        """
        Write an HID Output Report via pywinusb (Interface 0).
        This requires HidUsb driver on Interface 0.
        """
        if self.hid_device is None:
            return False
        try:
            out_reports = self.hid_device.find_output_reports()
            if out_reports:
                out_report = out_reports[0]
                # pywinusb expects a list with report ID at index 0
                out_report.set_raw_data(list(report))
                out_report.send()
                return True
        except Exception:
            pass
        return False

    def cleanup(self):
        """Release USB interfaces and close HID device."""
        if self.hid_device:
            try:
                self.hid_device.close()
            except Exception:
                pass
            self.hid_device = None

        if self.device:
            try:
                usb.util.release_interface(self.device, USB_INTERFACE_NUMBER)
            except Exception:
                pass
            try:
                usb.util.release_interface(self.device, 0)
            except Exception:
                pass
