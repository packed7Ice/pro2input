"""
main.py

Switch 2 Pro Controller -> Xbox 360 Input Converter
Entry point.  Combines USB input reading, XInput mapping, and HD Rumble feedback.

Requires:
    pip install pyusb vgamepad
    libusb-1.0.dll in C:\\Windows\\System32
    ViGEmBus driver installed
"""

import sys

from core.controller_usb import Switch2ProControllerUSB
from core.rumble_manager import RumbleManager
from mapping.xbox360_mapper import Xbox360Mapper
from config.settings import Settings


def main():
    # Load user settings
    settings = Settings()

    print("=" * 80)
    print(" Switch 2 Pro Controller -> Xbox 360 Input Converter")
    print(" With experimental HD Rumble feedback")
    print("=" * 80)

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
        print("[OK ] Rumble manager started (experimental).")
    else:
        print("\n[INFO] Rumble is disabled in config.")
        rumble = None

    print("\n[INFO] Starting input loop. Press Ctrl+C to stop.")
    print("[INFO] Open your game and enjoy!\n")

    # Step 4: Input loop
    try:
        while True:
            payload = controller.read_input(timeout=1000)
            if payload is not None:
                mapper.update_from_payload(payload)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        # Cleanup
        print("\n[INFO] Cleaning up...")
        if rumble:
            rumble.stop()
        controller.cleanup()
        mapper.reset()
        print("[OK ] Virtual controller reset.")
        print("Done.")


if __name__ == "__main__":
    main()
