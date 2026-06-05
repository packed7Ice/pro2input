"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller.
Uses a hybrid approach:
  - pyusb (libusb) for Interface 1 Bulk OUT/IN (initialization + rumble)
  - pywinusb (Windows HID API) for Interface 0 HID (input reading)

Interface 0 MUST be driven by HidUsb (Windows standard HID driver).
Interface 1 should have WinUSB or libusbK installed via Zadig.

CRITICAL initialization order (matches working test pattern):
  1. pyusb claim Interface 1, send init commands, read responses.
  2. Release Interface 1 claim (pywinusb needs this to open HID).
  3. Open Interface 0 via pywinusb for input reading.
  4. Keep pyusb device handle open for rumble bulk writes.
"""

import time
import usb.core
import usb.util

from pywinusb.hid import HidDeviceFilter

from core.constants import (
    TARGET_VID,
    TARGET_PID,
    USB_INTERFACE_NUMBER,
    INIT_COMMANDS,
    LED_COMMAND,
)

# Bulk transfer timeout (ms).  SDL uses 1000ms; we use 200ms for faster failure recovery.
_BULK_WRITE_TIMEOUT_MS = 200


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        # pyusb: opened once, kept alive for rumble bulk writes
        self._usb_device: usb.core.Device | None = None
        self._ep1_out = None
        self._ep1_in = None

        # pywinusb: used for Interface 0 input reading
        self.hid_device = None
        self._latest_input = None
        self._input_none_count = 0

    def find_and_connect(self) -> bool:
        """Find the controller."""
        self._usb_device = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
        if self._usb_device is None:
            return False
        return True

    def initialize_hid_mode(self) -> bool:
        """
        1. Claim Interface 1 via pyusb, send init commands, read responses.
        2. Release Interface 1 claim so pywinusb can open HID.
        3. Open Interface 0 (HID) via pywinusb.
        4. Keep pyusb device handle open for rumble bulk writes.
        """
        if self._usb_device is None:
            raise RuntimeError("Device not found. Call find_and_connect() first.")

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

        # Send SDL-validated init sequence
        for cmd in INIT_COMMANDS:
            try:
                self._usb_device.write(self._ep1_out, cmd, timeout=1000)
            except usb.core.USBError:
                pass
            time.sleep(0.05)
            try:
                if self._ep1_in:
                    self._usb_device.read(self._ep1_in, 64, timeout=100)
            except usb.core.USBError:
                pass

        # Send LED command after init (SDL OpenJoystick does this)
        try:
            self._usb_device.write(self._ep1_out, LED_COMMAND, timeout=1000)
        except usb.core.USBError:
            pass
        time.sleep(0.05)
        try:
            if self._ep1_in:
                self._usb_device.read(self._ep1_in, 64, timeout=100)
        except usb.core.USBError:
            pass

        # NOTE: Do NOT release Interface 1. libusb requires the interface
        # to remain claimed for bulk I/O. pywinusb can still open HID on
        # Interface 0 while Interface 1 is claimed by pyusb.

        # ---- Step 2: Open HID device via pywinusb ----
        devices = HidDeviceFilter(vendor_id=TARGET_VID, product_id=TARGET_PID).get_devices()
        if not devices:
            raise RuntimeError(
                "HID device not found. Make sure Interface 0 uses HidUsb (Windows standard HID driver)."
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
        if result is None:
            self._input_none_count += 1
            if self._input_none_count == 50:
                print("[USB] Warning: 50 consecutive read_input with no data")
        else:
            self._input_none_count = 0
        return result

    def send_rumble_bulk(self, packet: bytes) -> bool:
        """
        Send a 64-byte rumble packet via Interface 1 Bulk OUT.
        Uses a short timeout (200ms) so failures don't block the main loop.
        Attempts to clear HALT on the endpoint if a timeout occurs.
        """
        if self._usb_device is None or self._ep1_out is None:
            return False
        try:
            self._usb_device.write(self._ep1_out, packet, timeout=_BULK_WRITE_TIMEOUT_MS)
            return True
        except usb.core.USBError as exc:
            # If the endpoint is stalled, try to clear it once
            if exc.errno == 32:  # Pipe error / stall
                try:
                    usb.util.clear_halt(self._usb_device, self._ep1_out)
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def write_output_report(self, report: bytes) -> bool:
        """
        Write an HID Output Report via pywinusb.
        NOTE: This currently does not work for Switch 2 Pro (Write timed out).
        Kept for compatibility but send_rumble_bulk() should be used for rumble.
        """
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
        """Close HID device and dispose pyusb resources."""
        if self.hid_device:
            try:
                self.hid_device.close()
            except Exception:
                pass
            self.hid_device = None

        if self._usb_device is not None:
            try:
                usb.util.release_interface(self._usb_device, USB_INTERFACE_NUMBER)
            except Exception:
                pass
            try:
                usb.util.dispose_resources(self._usb_device)
            except Exception:
                pass
            self._usb_device = None
