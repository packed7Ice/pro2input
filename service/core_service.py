"""
service/core_service.py

Headless entry point for the desktop-app backend: identical device/rumble/
mapping orchestration to main.py, plus a WebSocket status server for the
Tauri UI. main.py is left completely untouched so the existing bat-launched
console path keeps working exactly as before.

Requires:
    pip install pyusb vgamepad websockets
    libusb-1.0.dll in C:\\Windows\\System32
    ViGEmBus driver installed
"""

import sys
import time
import argparse
import ctypes

from core.controller_usb import Switch2ProControllerUSB
from core.rumble_manager import RumbleManager
from core.rumble_udp_listener import FH6RumbleUDPListener
from core.input_parser import parse_buttons, parse_sticks
from core.constants import STICK_SCALE
from mapping.xbox360_mapper import Xbox360Mapper
from config.settings import Settings
from service.status_state import StatusState
from service.status_server import StatusServer
from service.settings_handler import SettingsCommandHandler

STATUS_PUSH_INTERVAL_SEC = 1.0 / 30  # throttle status snapshot updates to ~30Hz

_BUTTON_KEYS = [
    'Y', 'X', 'B', 'A', 'R', 'ZR',
    'Minus', 'Plus', 'RStick', 'LStick', 'Home', 'Capture', 'CButton',
    'Down', 'Up', 'Right', 'Left', 'L', 'ZL',
    'GRButton', 'GLButton',
]


def _default_buttons() -> dict:
    return {k: False for k in _BUTTON_KEYS}


def _default_sticks() -> dict:
    return {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}


def main():
    # Improve Windows timer resolution for accurate 1ms sleeps
    # (required so time.sleep(0.001) actually yields ~1ms, not ~15ms)
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Switch 2 Pro Controller -> Xbox 360 Input Converter (headless service)"
    )
    parser.add_argument("--no-udp", action="store_true", help="Disable FH6 UDP telemetry rumble")
    args = parser.parse_args()

    # Load user settings
    settings = Settings()

    print("=" * 80)
    print(" pro2input core service (headless backend for the desktop UI)")
    print(" With experimental HD Rumble 2 feedback")
    print("=" * 80)

    # Status server: start early so the UI can show "searching" state
    # even before the physical controller is found.
    status_state = StatusState()
    status_state.update(
        connected=False,
        rumble={"large": 0.0, "small": 0.0, "stalled": False, "suspended": False},
        input={"buttons": _default_buttons(), "sticks": _default_sticks()},
    )
    command_handler = SettingsCommandHandler(settings, rumble=None)
    status_server = StatusServer(status_state, command_handler=command_handler)
    status_server.start()
    print(f"\n[INFO] Status server listening on ws://127.0.0.1:{status_server.port}")

    # Step 1: Create virtual Xbox 360 controller
    print("\n[INFO] Creating virtual Xbox 360 controller...")
    mapper = Xbox360Mapper(settings=settings)
    print("[OK ] Virtual Xbox 360 controller created.")

    # Step 2: Find and initialize physical controller
    print("\n[INFO] Searching for Switch 2 Pro Controller...")
    controller = Switch2ProControllerUSB()
    if not controller.find_and_connect():
        print("[FATAL] Device not found.")
        print("\nChecklist:")
        print("  1. Is the controller connected via USB?")
        print("  2. Is the controller powered on?")
        print("  3. Are drivers (libusbK) correctly installed via Zadig?")
        sys.exit(1)

    print("[OK ] Device found.")
    controller.initialize_hid_mode()
    print("[OK ] Controller initialized and HID mode enabled.")

    # Step 3: Setup rumble feedback
    rumble_enabled = settings.get("rumble.enabled", True)
    if rumble_enabled:
        strength = settings.get("rumble.strength", 1.0)
        print(f"\n[INFO] Initializing rumble feedback manager (strength={strength})...")
        rumble = RumbleManager(controller, strength=strength)
        mapper.register_rumble_callback(rumble.on_xinput_rumble)
        rumble.start()
        command_handler.rumble = rumble
        print("[OK ] Rumble manager started (experimental).")
    else:
        print("\n[INFO] Rumble is disabled in config.")
        rumble = None

    # Step 3b: Setup FH6 UDP telemetry listener
    udp_listener = None
    if rumble_enabled and rumble is not None and not args.no_udp:
        udp_enabled = settings.get("fh6_udp.enabled", True)
        if udp_enabled:
            udp_port = settings.get("fh6_udp.port", 5301)
            udp_strength = settings.get("fh6_udp.strength", 1.0)
            udp_threshold = settings.get("fh6_udp.smashable_threshold", 3.0)
            udp_slip = settings.get("fh6_udp.slip_scale", 0.8)
            udp_surface = settings.get("fh6_udp.surface_scale", 1.0)
            udp_timeout = settings.get("fh6_udp.timeout_ms", 300)
            print(f"\n[INFO] Starting FH6 UDP telemetry listener on port {udp_port}...")
            try:
                udp_hold = settings.get("fh6_udp.hold_ms", 150)
                udp_listener = FH6RumbleUDPListener(
                    rumble,
                    port=udp_port,
                    strength=udp_strength,
                    smashable_threshold=udp_threshold,
                    slip_scale=udp_slip,
                    surface_scale=udp_surface,
                    timeout_ms=udp_timeout,
                    hold_ms=udp_hold,
                )
                udp_listener.start()
                rumble.ignore_xinput = True
                print("[OK ] FH6 UDP listener started.")
                print("[INFO] XInput rumble events will be ignored (UDP takes priority).")
            except OSError as exc:
                print(f"[WARN] Could not start UDP listener: {exc}")
                udp_listener = None
        else:
            print("\n[INFO] FH6 UDP telemetry is disabled in config.")
    elif args.no_udp:
        print("\n[INFO] FH6 UDP telemetry disabled by --no-udp flag.")

    print("\n[INFO] Starting input loop. Press Ctrl+C to stop.")
    print("[INFO] Open your game and enjoy!\n")

    last_buttons = _default_buttons()
    last_sticks = _default_sticks()
    last_status_push = 0.0

    # Step 4: Input loop with auto-reconnect (identical structure to main.py)
    try:
        while True:
            if rumble:
                rumble.drain_and_send()
            payload = controller.read_input(timeout=100)
            if payload is not None:
                mapper.update_from_payload(payload)
                last_buttons = parse_buttons(payload)
                lx, ly, rx, ry = parse_sticks(payload)
                last_sticks = {
                    "lx": lx / STICK_SCALE,
                    "ly": ly / STICK_SCALE,
                    "rx": rx / STICK_SCALE,
                    "ry": ry / STICK_SCALE,
                }

            # Auto-reconnect when controller is physically disconnected
            if not controller.is_connected:
                print("\n[WARN] Controller disconnected. Waiting for reconnect...")
                if rumble:
                    rumble.stop()
                mapper.reset()
                controller.cleanup()
                retry_delay = 1.0
                while True:
                    time.sleep(retry_delay)
                    if controller.find_and_connect():
                        try:
                            controller.initialize_hid_mode()
                            print("[OK ] Controller reconnected.")
                            break
                        except Exception as e:
                            print(f"[WARN] Reconnect init failed: {e}")
                    retry_delay = min(retry_delay * 1.5, 10.0)

            now = time.time()
            if now - last_status_push >= STATUS_PUSH_INTERVAL_SEC:
                large, small = rumble.get_intensity() if rumble else (0.0, 0.0)
                status_state.update(
                    connected=controller.is_connected,
                    rumble={
                        "large": large,
                        "small": small,
                        "stalled": controller.rumble_stalled,
                        "suspended": controller.rumble_suspended,
                    },
                    input={"buttons": last_buttons, "sticks": last_sticks},
                )
                last_status_push = now

            time.sleep(0.001)  # yield CPU ~1ms
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        # Cleanup
        print("\n[INFO] Cleaning up...")
        try:
            if udp_listener:
                udp_listener.stop()
        except Exception:
            pass
        try:
            if rumble:
                rumble.stop()
        except Exception:
            pass
        try:
            controller.cleanup()
        except Exception:
            pass
        try:
            mapper.reset()
        except Exception:
            pass
        print("[OK ] Virtual controller reset.")
        # Restore Windows timer resolution
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        print("Done.")


if __name__ == "__main__":
    main()
