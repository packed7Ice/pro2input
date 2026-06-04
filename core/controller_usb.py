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

        # Find Interface 0 IN endpoint for input reading
        intf0 = usb.util.find_descriptor(self.cfg, bInterfaceNumber=0)
        if intf0 is None:
            raise RuntimeError("Interface 0 not found")

        self.ep0_in = usb.util.find_descriptor(
            intf0,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )
        if self.ep0_in is None:
            raise RuntimeError("Interrupt IN endpoint not found on Interface 0")

        # Claim Interface 0 for reading input reports
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

    def send_hid_output_report(self, report_id: int, data: bytes) -> bool:
        """
        Send an HID Output Report via USB Control Transfer (SET_REPORT).

        For Switch 2 Pro rumble, the report must be exactly 64 bytes and use
        report ID 0x02.  This method works regardless of whether Interface 0
        is claimed by libusb or the Windows HID driver.

        bmRequestType = 0x21 (HID class, host->device, interface)
        bRequest      = 0x09 (SET_REPORT)
        wValue        = 0x02RR (Output Report, Report ID = RR)
        wIndex        = 0 (Interface 0)
        data          = [ReportID] + payload, padded to report byte length
        """
        if self.device is None:
            return False
        # Determine expected report size from device descriptor if possible,
        # otherwise default to 64 bytes (Switch 2 Pro standard).
        report_size = 64
        payload = bytes([report_id]) + data
        if len(payload) < report_size:
            payload = payload + bytes(report_size - len(payload))
        elif len(payload) > report_size:
            payload = payload[:report_size]

        try:
            self.device.ctrl_transfer(
                bmRequestType=0x21,   # HID class, host->device, interface
                bRequest=0x09,        # SET_REPORT
                wValue=(0x0200 | report_id),  # Output Report type + ID
                wIndex=0,             # Interface 0
                data_or_wLength=payload
            )
            return True
        except usb.core.USBError as e:
            # Some backends require wIndex=0 even if interface is 1.
            # Try again with wIndex=1 as fallback.
            try:
                self.device.ctrl_transfer(
                    bmRequestType=0x21,
                    bRequest=0x09,
                    wValue=(0x0200 | report_id),
                    wIndex=1,
                    data_or_wLength=payload
                )
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
