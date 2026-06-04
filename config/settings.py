"""
config/settings.py

Configuration management for pro2input.
Settings are persisted as JSON in `config.json`.
"""

import json
import os
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
        "ZR": "RIGHT_TRIGGER",
        "Plus": "START",
        "RStick": "RIGHT_THUMB",
        "Down": "DPAD_DOWN",
        "Right": "DPAD_RIGHT",
        "Left": "DPAD_LEFT",
        "Up": "DPAD_UP",
        "L": "LEFT_SHOULDER",
        "ZL": "LEFT_TRIGGER",
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
}


class Settings:
    """Manages loading, saving, and accessing configuration."""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = {}
        self.load()

    def load(self):
        """Load config from JSON file, or create default if missing."""
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
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        """Dot-notation access to nested values, e.g. 'stick.left.invert_y'."""
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
        keys = key.split(".")
        target = self.data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def reset_to_defaults(self):
        """Reset all settings to factory defaults."""
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
