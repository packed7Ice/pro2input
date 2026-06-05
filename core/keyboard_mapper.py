"""
core/keyboard_mapper.py

Simulates keyboard input for Switch 2 Pro buttons that have no Xbox 360 equivalent:
  Capture  (screenshot button)
  CButton  (game chat button)
  GRButton (right back grip button)
  GLButton (left back grip button)

Key combo format in config.json:
  Single key     : "f12", "prtsc", "esc"
  Modifier combo : "ctrl+s", "win+g", "win+alt+prtsc", "ctrl+shift+s"

Modifiers: ctrl, shift, alt, win (or super/cmd)

Requires: pip install pynput
"""

try:
    from pynput.keyboard import Key, Controller as _KbController
    _PYNPUT_AVAILABLE = True
except ImportError:
    _PYNPUT_AVAILABLE = False
    _KbController = None
    Key = None


_MODIFIER_TOKENS = {"ctrl", "control", "shift", "alt", "win", "super", "cmd"}

_MODIFIER_MAP = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "win": "cmd", "super": "cmd", "cmd": "cmd",
}

_SPECIAL_KEYS = {
    "prtsc": "print_screen", "print_screen": "print_screen",
    "esc": "esc", "escape": "esc",
    "tab": "tab",
    "enter": "enter", "return": "enter",
    "backspace": "backspace",
    "delete": "delete", "del": "delete",
    "insert": "insert",
    "home": "home",
    "end": "end",
    "pgup": "page_up", "page_up": "page_up",
    "pgdn": "page_down", "page_down": "page_down",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "space": "space",
    "pause": "pause",
    "caps_lock": "caps_lock",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
    "f13": "f13", "f14": "f14", "f15": "f15",
    "num0": "num0", "num1": "num1", "num2": "num2",
    "num3": "num3", "num4": "num4", "num5": "num5",
    "num6": "num6", "num7": "num7", "num8": "num8", "num9": "num9",
}


def _resolve_key(token: str):
    """Convert a key token string to a pynput Key or character."""
    t = token.strip().lower()
    if t in _SPECIAL_KEYS:
        return getattr(Key, _SPECIAL_KEYS[t])
    if len(t) == 1:
        return t
    try:
        return getattr(Key, t)
    except AttributeError:
        return t


def _parse_combo(combo_str: str) -> tuple[list, object] | None:
    """
    Parse "ctrl+shift+s" -> ([Key.ctrl, Key.shift], 's').
    Returns None if the combo string is empty or unparseable.
    """
    if not combo_str:
        return None
    parts = [p.strip().lower() for p in combo_str.split("+")]
    modifiers = []
    key = None
    for part in parts:
        if part in _MODIFIER_MAP:
            attr = _MODIFIER_MAP[part]
            modifiers.append(getattr(Key, attr))
        else:
            key = _resolve_key(part)
    if key is None:
        return None
    return modifiers, key


class KeyboardMapper:
    """
    Converts unmapped Switch 2 Pro button events to keyboard input.
    Triggers on the rising edge (button press moment) only — one shot per press.

    Usage:
        mapper = KeyboardMapper()
        # each input frame:
        mapper.update(buttons_dict, keyboard_mapping_from_config)
    """

    def __init__(self):
        self._available = _PYNPUT_AVAILABLE
        self._kb = _KbController() if _PYNPUT_AVAILABLE else None
        if not _PYNPUT_AVAILABLE:
            print("[KB] pynput not installed — keyboard mapping disabled.")
            print("[KB] Run: pip install pynput")
        self._prev_states: dict[str, bool] = {}

    def update(self, buttons: dict[str, bool], mapping: dict[str, str | None]):
        """
        Called every input frame. Fires the configured key combo on button press.
        buttons : output of input_parser.parse_buttons()
        mapping : config keyboard_mapping dict (button name -> combo string or None)
        """
        if not self._available or not mapping:
            return
        for button, combo in mapping.items():
            if not combo:
                continue
            current = buttons.get(button, False)
            was = self._prev_states.get(button, False)
            if current and not was:
                self._fire(combo)
            self._prev_states[button] = current

    def _fire(self, combo_str: str):
        result = _parse_combo(combo_str)
        if result is None:
            print(f"[KB] Cannot parse combo: '{combo_str}'")
            return
        modifiers, key = result
        try:
            for mod in modifiers:
                self._kb.press(mod)
            self._kb.press(key)
            self._kb.release(key)
            for mod in reversed(modifiers):
                self._kb.release(mod)
        except Exception as exc:
            print(f"[KB] Failed to send '{combo_str}': {exc}")
