"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller.
Uses a hybrid approach matching the working test_bulk_rumble.py pattern:
  - pyusb (libusb) for Interface 1 Bulk OUT/IN (initialization + rumble)
  - pywinusb (Windows HID API) for Interface 0 HID (input reading)

CRITICAL lessons from testing:
  1. Do NOT release Interface 1 claim — libusb needs it for Bulk I/O.
  2. pywinusb can open Interface 0 (HID) even while Interface 1 is claimed.
  3. Opening HID via pywinusb does NOT block pyusb Bulk OUT (confirmed in test).

Interface 0: Windows HID driver (HidUsb) — used by pywinusb.
Interface 1: WinUSB/libusbK via Zadig — used by pyusb.
"""

import time
import usb.core
import usb.util

from pywinusb.hid import HidDeviceFilter

from core.constants import (
    TARGET_VID,
    TARGET_PID,
    USB_INTERFACE_NUMBER,
    READ_FLASH_COMMANDS,
    INIT_COMMANDS,
    LED_COMMAND,
)

_BULK_WRITE_TIMEOUT_MS = 200


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        self._usb_device: usb.core.Device | None = None
        self._ep_bulk_out = None
        self._ep_bulk_in = None

        # pywinusb
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
        Working pattern (matches test_bulk_rumble.py):
          1. pyusb: claim Interface 1, send init + ReadFlashBlock, read responses.
          2. pyusb: keep Interface 1 claimed (NEVER release — needed for Bulk I/O).
          3. pywinusb: open Interface 0 (HID) for input reading.
        """
        if self._usb_device is None:
            raise RuntimeError("Device not found. Call find_and_connect() first.")

        self._usb_device.set_configuration()
        cfg = self._usb_device.get_active_configuration()

        # ---- Find Interface 1 endpoints ----
        intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
        if intf1 is None:
            raise RuntimeError("Interface 1 not found")

        for ep in intf1:
            direction = usb.util.endpoint_direction(ep.bEndpointAddress)
            if direction == usb.util.ENDPOINT_OUT:
                self._ep_bulk_out = ep.bEndpointAddress
            elif direction == usb.util.ENDPOINT_IN:
                self._ep_bulk_in = ep.bEndpointAddress

        if self._ep_bulk_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")

        # Claim Interface 1
        try:
            usb.util.claim_interface(self._usb_device, USB_INTERFACE_NUMBER)
        except usb.core.USBError:
            pass

        # ---- Send ReadFlashBlock commands (SDL does this before init) ----
        for flash_cmd in READ_FLASH_COMMANDS:
            try:
                self._usb_device.write(self._ep_bulk_out, flash_cmd, timeout=1000)
            except usb.core.USBError:
                pass
            time.sleep(0.05)
            try:
                if self._ep_bulk_in:
                    self._usb_device.read(self._ep_bulk_in, 64, timeout=100)
            except usb.core.USBError:
                pass

        # ---- Send init commands via Bulk OUT ----
        for cmd in INIT_COMMANDS:
            send_len = cmd[5] + 8
            to_send = cmd[:send_len]
            try:
                self._usb_device.write(self._ep_bulk_out, to_send, timeout=1000)
            except usb.core.USBError:
                pass
            time.sleep(0.05)
            try:
                if self._ep_bulk_in:
                    self._usb_device.read(self._ep_bulk_in, 64, timeout=100)
            except usb.core.USBError:
                pass

        # LED command
        try:
            self._usb_device.write(self._ep_bulk_out, LED_COMMAND, timeout=1000)
        except usb.core.USBError:
            pass
        time.sleep(0.05)
        try:
            if self._ep_bulk_in:
                self._usb_device.read(self._ep_bulk_in, 64, timeout=100)
        except usb.core.USBError:
            pass

        # ---- Step 2: Open HID device via pywinusb ----
        # Interface 1 stays claimed. pywinusb accesses Interface 0 independently.
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
        """Send a 64-byte rumble packet via Interface 1 Bulk OUT."""
        if self._usb_device is None or self._ep_bulk_out is None:
            return False
        try:
            self._usb_device.write(
                self._ep_bulk_out, packet, timeout=_BULK_WRITE_TIMEOUT_MS
            )
            return True
        except usb.core.USBError as exc:
            if exc.errno == 32:
                try:
                    usb.util.clear_halt(self._usb_device, self._ep_bulk_out)
                except Exception:
                    pass
            return False
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
