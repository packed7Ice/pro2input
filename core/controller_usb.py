"""
core/controller_usb.py

Handles USB communication with the Switch 2 Pro Controller using pyusb only.

Confirmed working endpoints (from rumble_comprehensive_test.py Test 5):
  Interface 0  ep 0x81  Interrupt IN   - HID input reports
  Interface 0  ep 0x01  Interrupt OUT  - Rumble output reports  ← KEY
  Interface 1  ep 0x02  Bulk OUT       - Init commands only
  Interface 1  ep 0x82  Bulk IN        - Init responses

Architecture:
  - Input reading runs in a dedicated daemon thread (blocking Interrupt IN read).
    This avoids blocking the main loop and prevents input lag.
  - Rumble goes via Interface 0 Interrupt OUT (ep 0x01).
    Bulk OUT (ep 0x02) is NOT used for rumble.
  - Both Interface 0 and Interface 1 are claimed at startup and kept claimed.
"""

import queue
import threading
import time
import usb.core
import usb.util

from core.constants import (
    TARGET_VID,
    TARGET_PID,
    USB_INTERFACE_NUMBER,
    READ_FLASH_COMMANDS,
    INIT_COMMANDS,
    LED_COMMAND,
)

_RUMBLE_TIMEOUT_MS = 50
_BULK_WRITE_TIMEOUT_MS = 200
_INPUT_READ_SIZE = 64
_INPUT_READ_TIMEOUT_MS = 100


class Switch2ProControllerUSB:
    """Manages USB connection and communication with Switch 2 Pro Controller."""

    def __init__(self):
        self._usb_device: usb.core.Device | None = None

        # Interface 0 endpoints (HID)
        self._ep0_in: int | None = None    # Interrupt IN  - input reports
        self._ep0_out: int | None = None   # Interrupt OUT - rumble

        # Interface 1 endpoints (Bulk proprietary)
        self._ep_bulk_out: int | None = None
        self._ep_bulk_in: int | None = None

        # Input thread
        self._input_queue: queue.Queue[list] = queue.Queue(maxsize=8)
        self._input_thread: threading.Thread | None = None
        self._running = False
        self._input_none_count = 0

    def find_and_connect(self) -> bool:
        self._usb_device = usb.core.find(idVendor=TARGET_VID, idProduct=TARGET_PID)
        return self._usb_device is not None

    def initialize_hid_mode(self) -> bool:
        if self._usb_device is None:
            raise RuntimeError("Device not found. Call find_and_connect() first.")

        self._usb_device.set_configuration()
        cfg = self._usb_device.get_active_configuration()

        # ---- Discover Interface 0 endpoints ----
        intf0 = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
        if intf0 is None:
            raise RuntimeError("Interface 0 not found")
        for ep in intf0:
            d = usb.util.endpoint_direction(ep.bEndpointAddress)
            if d == usb.util.ENDPOINT_IN:
                self._ep0_in = ep.bEndpointAddress
            elif d == usb.util.ENDPOINT_OUT:
                self._ep0_out = ep.bEndpointAddress

        if self._ep0_in is None or self._ep0_out is None:
            raise RuntimeError(
                f"Interface 0 missing endpoints: IN={self._ep0_in} OUT={self._ep0_out}"
            )

        # ---- Discover Interface 1 endpoints ----
        intf1 = usb.util.find_descriptor(cfg, bInterfaceNumber=USB_INTERFACE_NUMBER)
        if intf1 is None:
            raise RuntimeError("Interface 1 not found")
        for ep in intf1:
            d = usb.util.endpoint_direction(ep.bEndpointAddress)
            if d == usb.util.ENDPOINT_OUT:
                self._ep_bulk_out = ep.bEndpointAddress
            elif d == usb.util.ENDPOINT_IN:
                self._ep_bulk_in = ep.bEndpointAddress

        if self._ep_bulk_out is None:
            raise RuntimeError("Bulk OUT endpoint not found on Interface 1")

        # ---- Claim both interfaces ----
        for intf_num in (0, USB_INTERFACE_NUMBER):
            try:
                usb.util.claim_interface(self._usb_device, intf_num)
            except usb.core.USBError:
                pass

        # ---- Send ReadFlashBlock commands (before init, per SDL) ----
        for flash_cmd in READ_FLASH_COMMANDS:
            self._bulk_write(flash_cmd)
            time.sleep(0.05)
            self._bulk_read_response()

        # ---- Send init commands via Bulk OUT ----
        for cmd in INIT_COMMANDS:
            send_len = cmd[5] + 8
            self._bulk_write(cmd[:send_len])
            time.sleep(0.05)
            self._bulk_read_response()

        # ---- LED command ----
        self._bulk_write(LED_COMMAND)
        time.sleep(0.05)
        self._bulk_read_response()

        # ---- Start input reader thread ----
        self._running = True
        self._input_thread = threading.Thread(
            target=self._input_loop, daemon=True, name="USB-InputReader"
        )
        self._input_thread.start()

        return True

    def _bulk_write(self, data: bytes):
        if self._ep_bulk_out is None:
            return
        try:
            self._usb_device.write(self._ep_bulk_out, data, timeout=_BULK_WRITE_TIMEOUT_MS)
        except usb.core.USBError:
            pass

    def _bulk_read_response(self):
        if self._ep_bulk_in is None:
            return
        try:
            self._usb_device.read(self._ep_bulk_in, 64, timeout=100)
        except usb.core.USBError:
            pass

    def _input_loop(self):
        """
        Dedicated daemon thread: blocking Interrupt IN reads from Interface 0.
        Queues parsed payloads (Report ID stripped) for the main loop.
        """
        while self._running:
            try:
                raw = self._usb_device.read(
                    self._ep0_in, _INPUT_READ_SIZE, timeout=_INPUT_READ_TIMEOUT_MS
                )
                payload = list(bytes(raw))[1:]  # strip Report ID byte 0
                if self._input_queue.full():
                    try:
                        self._input_queue.get_nowait()  # discard oldest
                    except queue.Empty:
                        pass
                self._input_queue.put_nowait(payload)
            except usb.core.USBError:
                pass
            except Exception:
                pass

    def read_input(self, timeout: int = 100) -> list | None:
        """Non-blocking: return the latest input payload, or None."""
        try:
            result = self._input_queue.get_nowait()
            self._input_none_count = 0
            return result
        except queue.Empty:
            self._input_none_count += 1
            if self._input_none_count == 50:
                print("[USB] Warning: 50 consecutive read_input with no data")
            return None

    def send_rumble_bulk(self, packet: bytes) -> bool:
        """
        Send a 64-byte rumble packet via Interface 0 Interrupt OUT (ep 0x01).
        Rumble must go to the HID interrupt endpoint, NOT Interface 1 Bulk OUT.
        """
        if self._usb_device is None or self._ep0_out is None:
            return False
        try:
            self._usb_device.write(
                self._ep0_out, packet, timeout=_RUMBLE_TIMEOUT_MS
            )
            return True
        except usb.core.USBError as exc:
            if exc.errno == 32:
                try:
                    usb.util.clear_halt(self._usb_device, self._ep0_out)
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def cleanup(self):
        self._running = False
        if self._input_thread is not None:
            self._input_thread.join(timeout=0.5)
            self._input_thread = None

        if self._usb_device is not None:
            for intf_num in (0, USB_INTERFACE_NUMBER):
                try:
                    usb.util.release_interface(self._usb_device, intf_num)
                except Exception:
                    pass
            try:
                usb.util.dispose_resources(self._usb_device)
            except Exception:
                pass
            self._usb_device = None
