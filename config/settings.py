"""
config/settings.py

Configuration management for pro2input.
Settings are persisted as JSON in `config.json`.
"""

import json
import os
import threading
from pathlib import Path

CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "version": 1,
    "button_mapping": {
        "B": "B",
        "A": "A",
        "Y": "Y",
        "X": "X",
        "R": "RIGHT_SHOULDER",
        "ZR": None,          # ZR is analog trigger, handled separately
        "Plus": "START",
        "RStick": "RIGHT_THUMB",
        "Down": "DPAD_DOWN",
        "Right": "DPAD_RIGHT",
        "Left": "DPAD_LEFT",
        "Up": "DPAD_UP",
        "L": "LEFT_SHOULDER",
        "ZL": None,          # ZL is analog trigger, handled separately
        "Minus": "BACK",
        "LStick": "LEFT_THUMB",
        "Home": "GUIDE",
        "Capture": None,
        "CButton": None,
        "GRButton": None,
    },
    "stick": {
        "left": {"invert_x": False, "invert_y": False},
        "right": {"invert_x": False, "invert_y": True},
    },
    "trigger": {
        "synthesize_from_buttons": True,
    },
    "rumble": {
        "enabled": True,
        "strength": 1.0,
    },
    "fh6_udp": {
        "enabled": True,
        "port": 5301,
        "strength": 1.0,
        "smashable_threshold": 3.0,
        "slip_scale": 0.8,
        "surface_scale": 1.0,
        "timeout_ms": 300,
        "hold_ms": 150,
    },
    # Keyboard combos for buttons not mapped to Xbox 360.
    # Format: "ctrl+s", "win+alt+prtsc", "f12", or null to disable.
    # Available buttons: Capture, CButton, GRButton, GLButton
    "keyboard_mapping": {
        "Capture": "win+alt+prtsc",  # Xbox Game Bar screenshot
        "CButton": None,
        "GRButton": None,
        "GLButton": None,
    },
}


class Settings:
    """Manages loading, saving, and accessing configuration."""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = {}
        # RLock (not Lock): load()/reset_to_defaults() call save() internally,
        # which would deadlock a non-reentrant lock.
        self._lock = threading.RLock()
        self.load()

    def load(self):
        """Load config from JSON file, or create default if missing."""
        with self._lock:
            if self.path.exists():
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    # Merge missing keys from defaults
                    self._merge_defaults(DEFAULT_CONFIG, self.data)
                except (json.JSONDecodeError, OSError):
                    self.data = DEFAULT_CONFIG.copy()
            else:
                self.data = DEFAULT_CONFIG.copy()
                self.save()

    def save(self):
        """Save current config to JSON file."""
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        """Dot-notation access to nested values, e.g. 'stick.left.invert_y'."""
        with self._lock:
            keys = key.split(".")
            value = self.data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value):
        """Dot-notation set."""
        with self._lock:
            keys = key.split(".")
            target = self.data
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value

    def reset_to_defaults(self):
        """Reset all settings to factory defaults."""
        with self._lock:
            self.data = DEFAULT_CONFIG.copy()
            self.save()

    @staticmethod
    def _merge_defaults(defaults: dict, current: dict):
        """Recursively add missing keys from defaults into current."""
        for key, value in defaults.items():
            if key not in current:
                current[key] = value
            elif isinstance(value, dict) and isinstance(current.get(key), dict):
                Settings._merge_defaults(value, current[key])
