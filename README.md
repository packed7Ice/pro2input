# Switch 2 Pro Controller to XInput Converter

A Python-based USB input converter that maps **Nintendo Switch 2 Pro Controller** inputs to a virtual **Xbox 360 (XInput)** gamepad on Windows.

## Features

- **Full Button Mapping** — Face buttons, shoulder buttons, D-Pad, system buttons
- **Analog Stick Support** — Both left and right sticks with correct axis polarity
- **Trigger Synthesis** — ZL/ZR digital buttons mapped to analog LT/RT triggers
- **HD Rumble Feedback** — Experimental force-feedback support via SDL-derived protocol
- **Modular Architecture** — Clean separation of USB transport, input parsing, and mapping layers

## Requirements

- Windows 10/11
- Python 3.10+
- Nintendo Switch 2 Pro Controller (USB connection)
- [ViGEmBus Driver](https://github.com/nefarius/ViGEmBus) (for virtual Xbox 360 controller)
- [libusb-1.0.dll](https://libusb.info/) (placed in `C:\Windows\System32`)
- [Zadig](https://zadig.akeo.ie/) (to install libusbK driver for Interface 1)

## Installation

```bash
# Clone the repository
git clone https://github.com/packed7Ice/pro2input.git
cd pro2input

# Install Python dependencies
pip install pyusb vgamepad
```

### Driver Setup (Zadig)

1. Connect your Switch 2 Pro Controller via USB.
2. Open Zadig, go to **Options → List All Devices**.
3. Select **"Switch Pro Controller"** (or similar).
4. For **Interface 1**, install the **libusbK** driver.
5. **Keep Interface 0 on the Windows HID driver** (`HidUsb`) for rumble support.

## Usage

Run the main converter:

```bash
python main.py
```

The script will:
1. Create a virtual Xbox 360 controller
2. Find and initialize the Switch 2 Pro Controller
3. Start the input loop with rumble feedback enabled

### Rumble Test

To verify rumble is working:

```bash
# Terminal 1: start the converter
python main.py

# Terminal 2: send test vibration
python tools/xinput_rumble_test.py
```

## Project Structure

```
pro2input/
├── main.py                      # Entry point
├── core/
│   ├── constants.py             # Device IDs, init commands, rumble constants
│   ├── controller_usb.py        # USB connection and HID I/O
│   ├── input_parser.py           # Button/stick/trigger parsing
│   └── rumble_manager.py         # XInput → Switch 2 Pro rumble conversion
├── mapping/
│   └── xbox360_mapper.py        # Virtual Xbox 360 gamepad mapping
├── tools/                       # Test & diagnostic scripts
├── docs/                        # Setup guides
└── LICENSE                      # Apache 2.0
```

## Tools

| Script | Purpose |
|--------|---------|
| `tools/button_test.py` | Verify button mapping |
| `tools/stick_raw_diagnostic.py` | Inspect raw stick values |
| `tools/xinput_rumble_test.py` | Test XInput force-feedback |
| `tools/rumble_hid_control_test.py` | Direct USB rumble debug |

## Troubleshooting

### Controller not found
- Ensure the controller is powered on and connected via USB.
- Verify the libusbK driver is installed for Interface 1 via Zadig.

### No input in games
- Make sure `main.py` is running. The virtual controller only exists while the script is active.
- Check that ViGEmBus is installed correctly.

### Rumble not working
- Ensure Interface 0 remains on the Windows HID driver (`HidUsb`).
- Run `tools/xinput_rumble_test.py` while `main.py` is active.

## Acknowledgments

- Rumble protocol derived from the official **SDL** implementation (`SDL_hidapi_switch2.c`).
- USB initialization sequence based on **NSW2-controller-enabler** by ikz87.

## License

This project is licensed under the **Apache License 2.0**.
See [LICENSE](LICENSE) for details.
