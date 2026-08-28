"""
service/settings_handler.py

Handles inbound WebSocket settings commands (get/set/reset) against the same
Settings instance the polling loop reads every tick.

button_mapping, stick.*.invert_*, and keyboard_mapping already apply live —
mapping/xbox360_mapper.py and core/keyboard_mapper.py both re-read
settings.get(...) fresh on every input tick. rumble.strength is pushed live
via RumbleManager.set_strength(). rumble.enabled and fh6_udp.* are only read
once at startup (to decide whether/how to construct RumbleManager /
FH6RumbleUDPListener) and require a core service restart to take effect.
"""

from mapping.xbox360_codes import XBOX_BUTTON_CODES, SWITCH_BUTTON_NAMES


class SettingsCommandHandler:
    """command_handler for StatusServer: get_settings / set_settings / reset_settings."""

    def __init__(self, settings, rumble=None):
        self.settings = settings
        # May be set later (rumble.py is constructed after the status server
        # starts, so this can be None at first and assigned once available).
        self.rumble = rumble

    def on_connect(self) -> dict | None:
        return self._settings_message()

    def handle(self, msg: dict) -> dict | None:
        msg_type = msg.get("type")

        if msg_type == "get_settings":
            return self._settings_message()

        if msg_type == "set_settings":
            values = msg.get("values")
            if not isinstance(values, dict):
                return None
            for key, value in values.items():
                self.settings.set(key, value)
            self.settings.save()
            if self.rumble is not None and "rumble.strength" in values:
                try:
                    self.rumble.set_strength(float(values["rumble.strength"]))
                except (TypeError, ValueError):
                    pass
            return self._settings_message()

        if msg_type == "reset_settings":
            self.settings.reset_to_defaults()
            return self._settings_message()

        return None

    def _settings_message(self) -> dict:
        return {
            "type": "settings",
            "data": self.settings.data,
            "meta": {
                "xbox_button_codes": sorted(XBOX_BUTTON_CODES.keys()),
                "switch_button_names": list(SWITCH_BUTTON_NAMES),
            },
        }
