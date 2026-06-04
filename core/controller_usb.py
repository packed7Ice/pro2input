"""
core/controller_usb.py

Handles low-level USB communication with the Switch 2 Pro Controller:
- Device discovery
- Sending initialization sequence (Interface 1 Bulk OUT)
- Claiming Interface 0 for HID input reading
- Sending output commands (e.g. rumble) via Interface 1
"""

import time
import usb.core
import usb.util

from core.constants import TARGET_VID, TARGET_PID, USB_INTERFACE_NUMBER, INIT_COMMANDS


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        self.device: usb.core.Device | None = None
        self.cfg = None
        self.ep0_in = None  # Interface 0 Interrupt IN endpoint
        self.ep1_out = None  # Interface 1 Bulk OUT endpoint
        self.ep1_in = None   # Interface 1 Bulk IN endpoint (optional)

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
        Send the initialization command sequence via Interface 1 (Bulk OUT)
        to enable HID report mode on Interface 0.
        """
        intf1 = usb.util.find_descriptor(self.cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
        if intf1 is None:
            raise RuntimeError("Interface 1 not found")

        # Find endpoints on Interface 1
        for ep in intf1:
            direction = usb.util.endpoint_direction(ep.bEndpointAddress)
            if direction == usb.util.ENDPOINT_OUT:
                self.ep1_out = ep.bEndpointAddress
            elif direction == usb.util.ENDPOINT_IN:
                self.ep1_in = ep.bEndpointAddress

        if self.ep1_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")

        # Claim Interface 1 for writing init commands
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

        # Find Interface 0 endpoints for input reading and output writing
        intf0 = usb.util.find_descriptor(self.cfg, bInterfaceNumber=0)
        if intf0 is None:
            raise RuntimeError("Interface 0 not found")

        self.ep0_in = None
        self.ep0_out = None
        for ep in intf0:
            direction = usb.util.endpoint_direction(ep.bEndpointAddress)
            if direction == usb.util.ENDPOINT_IN:
                self.ep0_in = ep
            elif direction == usb.util.ENDPOINT_OUT:
                self.ep0_out = ep

        if self.ep0_in is None:
            raise RuntimeError("Interrupt IN endpoint not found on Interface 0")

        # Claim Interface 0 for reading input reports and sending output reports
        try:
            usb.util.claim_interface(self.device, 0)
        except usb.core.USBError:
            pass

        return True

    def read_input(self, timeout: int = 1000) -> list | None:
        """Read an input report from Interface 0. Returns payload (list) or None."""
        if self.device is None or self.ep0_in is None:
            return None
        try:
            data = self.device.read(self.ep0_in.bEndpointAddress, 64, timeout=timeout)
            if data:
                return list(data)[1:]  # Skip Report ID
        except usb.core.USBError as e:
            if e.errno == 110 or e.errno == 10060:
                return None
            raise
        return None

    def write_output_report(self, report: bytes) -> bool:
        """
        Write an HID Output Report to Interface 0 Interrupt OUT endpoint.
        This is the correct transport for Switch 2 Pro rumble data.
        """
        if self.device is None or self.ep0_out is None:
            return False
        try:
            self.device.write(self.ep0_out.bEndpointAddress, report)
            return True
        except usb.core.USBError:
            return False

    def send_command(self, cmd: bytes) -> bool:
        """
        Send a raw command via Interface 1 Bulk OUT.
        Interface 1 is temporarily claimed because it was released after init.
        """
        if self.device is None or self.ep1_out is None:
            return False
        try:
            usb.util.claim_interface(self.device, USB_INTERFACE_NUMBER)
            self.device.write(self.ep1_out, cmd)
            usb.util.release_interface(self.device, USB_INTERFACE_NUMBER)
            return True
        except usb.core.USBError:
            return False

    def cleanup(self):
        """Release USB interfaces."""
        if self.device:
            try:
                usb.util.release_interface(self.device, 0)
            except Exception:
                pass
            try:
                usb.util.release_interface(self.device, USB_INTERFACE_NUMBER)
            except Exception:
                pass
