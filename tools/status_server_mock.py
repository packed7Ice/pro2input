"""
tools/status_server_mock.py

Throwaway smoke test for the status WebSocket pipeline, with no controller
hardware required. Feeds StatusState fake oscillating values on a timer and
starts StatusServer, so ui-app (or a plain WS client) can be pointed at it
to validate the schema/broadcast plumbing independent of USB.

Usage:
    python tools/status_server_mock.py
Then connect a client to ws://127.0.0.1:8765 and watch the values move.
"""

import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.status_state import StatusState
from service.status_server import StatusServer

_BUTTON_KEYS = [
    'Y', 'X', 'B', 'A', 'R', 'ZR',
    'Minus', 'Plus', 'RStick', 'LStick', 'Home', 'Capture', 'CButton',
    'Down', 'Up', 'Right', 'Left', 'L', 'ZL',
    'GRButton', 'GLButton',
]


def main():
    status_state = StatusState()
    status_server = StatusServer(status_state)
    status_server.start()
    print(f"[OK] Mock status server on ws://127.0.0.1:{status_server.port}")
    print("[INFO] Press Ctrl+C to stop.")

    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            large = (math.sin(t * 1.3) + 1) / 2
            small = (math.sin(t * 2.1 + 1.0) + 1) / 2
            connected = (int(t) % 20) < 17  # simulate occasional disconnects
            pressed_index = int(t * 2) % len(_BUTTON_KEYS)
            buttons = {k: (i == pressed_index) for i, k in enumerate(_BUTTON_KEYS)}
            status_state.update(
                connected=connected,
                rumble={
                    "large": large,
                    "small": small,
                    "stalled": (int(t) % 20) == 17,
                    "suspended": False,
                },
                input={
                    "buttons": buttons,
                    "sticks": {
                        "lx": math.sin(t * 0.7),
                        "ly": math.cos(t * 0.7),
                        "rx": math.sin(t * 0.5 + 2.0),
                        "ry": math.cos(t * 0.5 + 2.0),
                    },
                },
            )
            time.sleep(0.03)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped.")


if __name__ == "__main__":
    main()
