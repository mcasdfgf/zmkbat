"""Nerd Font glyphs used by the status-bar formatters.

The codepoints come from Material Design Icons (``nf-md-battery*``), which are
part of every Nerd Fonts release. Users without a Nerd Font can pass
``--ascii`` and get plain text instead.
"""

from __future__ import annotations

# (minimum percent, glyph), ordered from full to empty.
BATTERY_ICONS: tuple[tuple[int, str], ...] = (
    (95, "\U000f0079"),  # nf-md-battery
    (90, "\U000f0082"),  # nf-md-battery_90
    (80, "\U000f0081"),  # nf-md-battery_80
    (70, "\U000f0080"),  # nf-md-battery_70
    (60, "\U000f007f"),  # nf-md-battery_60
    (50, "\U000f007e"),  # nf-md-battery_50
    (40, "\U000f007d"),  # nf-md-battery_40
    (30, "\U000f007c"),  # nf-md-battery_30
    (20, "\U000f007b"),  # nf-md-battery_20
    (10, "\U000f007a"),  # nf-md-battery_10
    (0, "\U000f008e"),  # nf-md-battery_outline
)

BLUETOOTH_ICON = "\U000f00af"  # nf-md-bluetooth
UNKNOWN_ICON = "\U000f008e"  # nf-md-battery_outline


def battery_icon(percent: int | None) -> str:
    """Return the glyph that best matches ``percent``."""
    if percent is None:
        return UNKNOWN_ICON
    for threshold, glyph in BATTERY_ICONS:
        if percent >= threshold:
            return glyph
    return BATTERY_ICONS[-1][1]
