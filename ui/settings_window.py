"""
ui/settings_window.py

Simple tkinter-based settings GUI for pro2input.
Allows users to:
- Remap Switch buttons to Xbox 360 buttons
- Toggle stick axis inversion
- Enable/disable rumble and adjust strength
- Save/load configuration
"""

import tkinter as tk
from tkinter import ttk, messagebox

from config.settings import Settings, DEFAULT_CONFIG
from mapping.xbox360_codes import XBOX_BUTTON_CODES, SWITCH_BUTTON_NAMES


class SettingsWindow:
    """Tkinter settings editor window."""

    def __init__(self):
        self.settings = Settings()
        self.root = tk.Tk()
        self.root.title("pro2input Settings")
        self.root.geometry("600x700")
        self.root.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        # Title
        ttk.Label(self.root, text="pro2input Configuration", font=("Segoe UI", 16, "bold")).pack(pady=10)

        # Notebook (tabs)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 1: Button Mapping
        tab_buttons = ttk.Frame(notebook)
        notebook.add(tab_buttons, text="Button Mapping")
        self._build_button_mapping_tab(tab_buttons)

        # Tab 2: Stick Settings
        tab_sticks = ttk.Frame(notebook)
        notebook.add(tab_sticks, text="Sticks")
        self._build_stick_tab(tab_sticks)

        # Tab 3: Rumble
        tab_rumble = ttk.Frame(notebook)
        notebook.add(tab_rumble, text="Rumble")
        self._build_rumble_tab(tab_rumble)

        # Bottom buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Reset to Defaults", command=self._on_reset).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Exit", command=self.root.destroy).pack(side="left", padx=5)

    def _build_button_mapping_tab(self, parent):
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(scroll_frame, text="Switch Button", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(scroll_frame, text="→", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(scroll_frame, text="Xbox 360 Button", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=5, pady=5)

        xbox_options = ["(None)"] + sorted(XBOX_BUTTON_CODES.keys())
        self.mapping_vars = {}

        current_mapping = self.settings.get("button_mapping", DEFAULT_CONFIG["button_mapping"])

        for idx, switch_btn in enumerate(SWITCH_BUTTON_NAMES, start=1):
            ttk.Label(scroll_frame, text=switch_btn).grid(row=idx, column=0, padx=5, pady=2, sticky="e")
            ttk.Label(scroll_frame, text="→").grid(row=idx, column=1, padx=5, pady=2)

            var = tk.StringVar()
            mapped = current_mapping.get(switch_btn)
            var.set(mapped if mapped else "(None)")
            self.mapping_vars[switch_btn] = var

            combo = ttk.Combobox(scroll_frame, textvariable=var, values=xbox_options, state="readonly", width=20)
            combo.grid(row=idx, column=2, padx=5, pady=2, sticky="w")

    def _build_stick_tab(self, parent):
        ttk.Label(parent, text="Left Stick", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 5), padx=10)

        self.left_invert_x = tk.BooleanVar(value=self.settings.get("stick.left.invert_x", False))
        self.left_invert_y = tk.BooleanVar(value=self.settings.get("stick.left.invert_y", False))

        ttk.Checkbutton(parent, text="Invert X axis", variable=self.left_invert_x).pack(anchor="w", padx=20)
        ttk.Checkbutton(parent, text="Invert Y axis", variable=self.left_invert_y).pack(anchor="w", padx=20)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=15, padx=10)

        ttk.Label(parent, text="Right Stick", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(5, 5), padx=10)

        self.right_invert_x = tk.BooleanVar(value=self.settings.get("stick.right.invert_x", False))
        self.right_invert_y = tk.BooleanVar(value=self.settings.get("stick.right.invert_y", True))

        ttk.Checkbutton(parent, text="Invert X axis", variable=self.right_invert_x).pack(anchor="w", padx=20)
        ttk.Checkbutton(parent, text="Invert Y axis", variable=self.right_invert_y).pack(anchor="w", padx=20)

        ttk.Label(parent, text="Note: Y-axis inversion is typically needed because\n"
                                "Switch and Xbox use opposite polarities for stick Y.",
                  foreground="gray").pack(anchor="w", pady=20, padx=10)

    def _build_rumble_tab(self, parent):
        self.rumble_enabled = tk.BooleanVar(value=self.settings.get("rumble.enabled", True))
        ttk.Checkbutton(parent, text="Enable rumble feedback", variable=self.rumble_enabled).pack(anchor="w", padx=10, pady=10)

        ttk.Label(parent, text="Rumble Strength", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        self.rumble_strength = tk.DoubleVar(value=self.settings.get("rumble.strength", 1.0))
        scale = ttk.Scale(parent, from_=0.0, to=2.0, orient="horizontal", variable=self.rumble_strength, length=300)
        scale.pack(anchor="w", padx=10, pady=5)

        ttk.Label(parent, text="1.0 = normal, 0.0 = off, 2.0 = double strength", foreground="gray").pack(anchor="w", padx=10)


    def _on_save(self):
        # Save button mapping
        mapping = {}
        for switch_btn, var in self.mapping_vars.items():
            val = var.get()
            mapping[switch_btn] = val if val != "(None)" else None
        self.settings.set("button_mapping", mapping)

        # Save stick settings
        self.settings.set("stick.left.invert_x", self.left_invert_x.get())
        self.settings.set("stick.left.invert_y", self.left_invert_y.get())
        self.settings.set("stick.right.invert_x", self.right_invert_x.get())
        self.settings.set("stick.right.invert_y", self.right_invert_y.get())

        # Save rumble settings
        self.settings.set("rumble.enabled", self.rumble_enabled.get())
        self.settings.set("rumble.strength", round(self.rumble_strength.get(), 2))

        self.settings.save()
        messagebox.showinfo("Saved", "Configuration saved to config.json")

    def _on_reset(self):
        if messagebox.askyesno("Confirm Reset", "Reset all settings to defaults?"):
            self.settings.reset_to_defaults()
            # Rebuild UI with defaults
            for widget in self.root.winfo_children():
                widget.destroy()
            self.settings = Settings()
            self._build_ui()
            messagebox.showinfo("Reset", "Settings reset to defaults.")

    def run(self):
        self.root.mainloop()


def main():
    app = SettingsWindow()
    app.run()


if __name__ == "__main__":
    main()
