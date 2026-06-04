"""
tools/settings_ui.py

Launch the settings GUI for pro2input.
Allows button remapping, stick inversion, and rumble configuration.

Usage:
    python tools/settings_ui.py
"""

import sys
import os

# Add parent directory to path so imports work when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.settings_window import main

if __name__ == "__main__":
    main()
