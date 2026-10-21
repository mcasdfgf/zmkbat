"""zmkbat — battery levels for both halves of a ZMK split keyboard.

The package is intentionally small and dependency-light: it talks to BlueZ
over D-Bus, reads the standard GATT Battery Service and renders the result in
formats that are convenient for status bars (polybar, waybar, i3blocks) and
for scripts (plain text, JSON).
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
