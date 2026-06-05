"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller.
Uses pyusb (libusb) for ALL interfaces:
  - Interface 0 (HID): Interrupt IN for input reading
  - Interface 1 (Bulk): Bulk OUT for init + rumble, Bulk IN for responses

CRITICAL: pywinusb is NOT used. Opening the HID device via Windows HID API
prevents pyusb from using Bulk OUT. SDL uses libusb for everything.

Interface 1 should have WinUSB or libusbK installed via Zadig.
Interface 0 MUST remain on the Windows HID driver (HidUsb) in Device Manager,
but libusb will auto-detach it when we claim the interface.
"""

import time
import usb.core
import usb.util

from core.constants import (
    TARGET_VID,
    TARGET_PID,
    USB_INTERFACE_NUMBER,
    INIT_COMMANDS,
    LED_COMMAND,
)

# Interface numbers
_HID_INTERFACE = 0
_BULK_INTERFACE = 1

# Transfer timeouts
_BULK_WRITE_TIMEOUT_MS = 200
_HID_READ_TIMEOUT_MS = 100


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        self._usb_device: usb.core.Device | None = None
        self._ep_bulk_out = None
        self._ep_bulk_in = None
        self._ep_intr_in = None

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
        1. Enable auto-detach of kernel drivers (Windows HID driver).
        2. Set configuration and find endpoints.
        3. Claim BOTH interfaces (0 and 1).
        4. Send init commands via Bulk OUT.
        5. Start reading HID reports via Interrupt IN.
        """
        if self._usb_device is None:
            raise RuntimeError("Device not found. Call find_and_connect() first.")

        # Enable auto-detach so libusb can claim interfaces owned by Windows drivers
        try:
            self._usb_device.set_auto_detach_kernel_driver(True)
        except Exception:
            pass

        self._usb_device.set_configuration()
        cfg = self._usb_device.get_active_configuration()

        # ---- Find endpoints ----
        for intf in cfg:
            if intf.bInterfaceNumber == _HID_INTERFACE:
                for ep in intf:
                    direction = usb.util.endpoint_direction(ep.bEndpointAddress)
                    if direction == usb.util.ENDPOINT_IN:
                        self._ep_intr_in = ep.bEndpointAddress
            elif intf.bInterfaceNumber == _BULK_INTERFACE:
                for ep in intf:
                    direction = usb.util.endpoint_direction(ep.bEndpointAddress)
                    if direction == usb.util.ENDPOINT_OUT:
                        self._ep_bulk_out = ep.bEndpointAddress
                    elif direction == usb.util.ENDPOINT_IN:
                        self._ep_bulk_in = ep.bEndpointAddress

        if self._ep_bulk_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")
        if self._ep_intr_in is None:
            raise RuntimeError("Interrupt IN endpoint not found on Interface 0")

        # ---- Claim both interfaces ----
        for iface in (_HID_INTERFACE, _BULK_INTERFACE):
            try:
                usb.util.claim_interface(self._usb_device, iface)
            except usb.core.USBError:
                pass

        # ---- Send init commands via Bulk OUT ----
        for cmd in INIT_COMMANDS:
            try:
                self._usb_device.write(self._ep_bulk_out, cmd, timeout=1000)
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

        return True

    def read_input(self, timeout: int = 100) -> list | None:
        """
        Read HID input report via Interrupt IN (pyusb).
        Returns payload with Report ID skipped.
        """
        if self._usb_device is None or self._ep_intr_in is None:
            return None

        # First, try to read from the interrupt endpoint
        try:
            data = self._usb_device.read(self._ep_intr_in, 64, timeout=_HID_READ_TIMEOUT_MS)
            if data and len(data) >= 11:
                return list(bytes(data))[1:]  # Skip Report ID
        except usb.core.USBError as exc:
            if exc.errno == 10060:  # timeout
                pass  # No data available
            else:
                print(f"[USB] Interrupt read error: {exc}")
        except Exception:
            pass

        self._input_none_count += 1
        if self._input_none_count == 50:
            print("[USB] Warning: 50 consecutive read_input with no data")
        return None

    def send_rumble_bulk(self, packet: bytes) -> bool:
        """
        Send a 64-byte rumble packet via Interface 1 Bulk OUT.
        """
        if self._usb_device is None or self._ep_bulk_out is None:
            return False
        try:
            self._usb_device.write(
                self._ep_bulk_out, packet, timeout=_BULK_WRITE_TIMEOUT_MS
            )
            return True
        except usb.core.USBError as exc:
            if exc.errno == 32:  # Pipe error / stall
                try:
                    usb.util.clear_halt(self._usb_device, self._ep_bulk_out)
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def cleanup(self):
        """Release interfaces and dispose pyusb resources."""
        if self._usb_device is not None:
            for iface in (_BULK_INTERFACE, _HID_INTERFACE):
                try:
                    usb.util.release_interface(self._usb_device, iface)
                except Exception:
                    pass
            try:
                usb.util.dispose_resources(self._usb_device)
            except Exception:
                pass
            self._usb_device = None
