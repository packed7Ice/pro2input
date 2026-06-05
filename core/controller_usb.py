"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller.
Uses a hybrid approach:
  - pyusb (libusb) for Interface 1 Bulk OUT/IN (initialization commands)
  - pywinusb (Windows HID API) for Interface 0 HID (input reading + rumble output)

Interface 0 MUST be driven by HidUsb (Windows standard HID driver).
Interface 1 should have WinUSB or libusbK installed via Zadig.

Critical: after each init command, read the Bulk IN response (RecvBulkData)
to complete the handshake, otherwise the controller won't enter HID mode.
"""

import time
import usb.core
import usb.util

from pywinusb.hid import HidDeviceFilter

from core.constants import TARGET_VID, TARGET_PID, USB_INTERFACE_NUMBER, INIT_COMMANDS


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        # pyusb: only used for Interface 1 init, then released
        self._usb_device: usb.core.Device | None = None
        self._ep1_out = None
        self._ep1_in = None

        # pywinusb: used for Interface 0 input/output
        self.hid_device = None
        self._latest_input = None

    def find_and_connect(self) -> bool:
        """Find the controller."""
        self._usb_device = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
        if self._usb_device is None:
            return False
        return True

    def initialize_hid_mode(self) -> bool:
        """
        1. Send init commands via Interface 1 (Bulk OUT) using pyusb.
           Read response after each command (critical!).
        2. Release all pyusb resources.
        3. Open Interface 0 (HID) via pywinusb.
        """
        # ---- Step 1: pyusb Interface 1 init ----
        self._usb_device.set_configuration()
        cfg = self._usb_device.get_active_configuration()

        intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
        if intf1 is None:
            raise RuntimeError("Interface 1 not found")

        for ep in intf1:
            direction = usb.util.endpoint_direction(ep.bEndpointAddress)
            if direction == usb.util.ENDPOINT_OUT:
                self._ep1_out = ep.bEndpointAddress
            elif direction == usb.util.ENDPOINT_IN:
                self._ep1_in = ep.bEndpointAddress

        if self._ep1_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")

        try:
            usb.util.claim_interface(self._usb_device, USB_INTERFACE_NUMBER)
        except usb.core.USBError:
            pass

        for cmd in INIT_COMMANDS:
            try:
                self._usb_device.write(self._ep1_out, cmd)
            except usb.core.USBError:
                pass
            time.sleep(0.05)
            # Read response after each command (SDL does this)
            try:
                if self._ep1_in:
                    self._usb_device.read(self._ep1_in, 64, timeout=100)
            except usb.core.USBError:
                pass

        try:
            usb.util.release_interface(self._usb_device, USB_INTERFACE_NUMBER)
        except Exception:
            pass

        # Fully dispose pyusb resources so pywinusb can open the HID interface
        usb.util.dispose_resources(self._usb_device)
        self._usb_device = None

        # Give Windows a moment to re-enumerate
        time.sleep(0.5)

        # ---- Step 2: pywinusb Interface 0 open ----
        devices = HidDeviceFilter(vendor_id=TARGET_VID, product_id=TARGET_PID).get_devices()
        if not devices:
            raise RuntimeError(
                "HID device not found after init. "
                "Make sure Interface 0 uses HidUsb (Windows standard HID driver)."
            )

        self.hid_device = devices[0]
        self.hid_device.open()
        self.hid_device.set_raw_data_handler(self._on_input)
        return True

    def _on_input(self, data):
        """pywinusb callback: stores the latest input report."""
        self._latest_input = list(bytes(data))[1:]  # Skip Report ID

    def read_input(self, timeout: int = 100) -> list | None:
        """Return the latest captured input report."""
        if self.hid_device is None:
            return None
        result = self._latest_input
        self._latest_input = None
        return result

    def write_output_report(self, report: bytes) -> bool:
        """Write an HID Output Report via pywinusb."""
        if self.hid_device is None:
            return False
        try:
            out_reports = self.hid_device.find_output_reports()
            if not out_reports:
                return False
            out_report = out_reports[0]
            out_report.set_raw_data(list(report))
            out_report.send()
            return True
        except Exception:
            return False

    def cleanup(self):
        """Close HID device."""
        if self.hid_device:
            try:
                self.hid_device.close()
            except Exception:
                pass
            self.hid_device = None
