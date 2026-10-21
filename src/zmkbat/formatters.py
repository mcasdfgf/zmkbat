"""Render keyboards in the supported output formats.

Every formatter is a pure function of ``(keyboards, config)``, which keeps the
CLI thin and makes the output easy to test.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from .config import Config
from .icons import BLUETOOTH_ICON, battery_icon
from .model import Half, HalfState, Keyboard, half_state

BAR_WIDTH = 10

# Polybar colour tags. ``%{F-}`` resets to the bar's default foreground.
DIM = "%{F#555555}"
RESET = "%{F-}"
CRITICAL = "%{F#bd2c40}"
WARNING = "%{F#FFAA01}"

LABEL_WIDTH = 18


def format_age(seconds: int | None) -> str:
    """Compact, human-readable age: ``42s``, ``7m``, ``3h``, ``2d``."""
    if seconds is None:
        return "?"
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def format_bar(percent: int | None, width: int = BAR_WIDTH) -> str:
    """A unicode progress bar; dots when the value is unknown."""
    if percent is None:
        return "·" * width
    filled = max(0, min(width, round(percent * width / 100)))
    return "█" * filled + "░" * (width - filled)


def _state(half: Half, keyboard: Keyboard, config: Config) -> HalfState:
    return half_state(half, keyboard, zero_means_off=config.zero_means_off)


def _label(half: Half, config: Config) -> str:
    return config.label_for(half.role)


def _describe(half: Half) -> str:
    return f" ({half.label})" if half.label else ""


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------


def format_text(keyboards: Sequence[Keyboard], config: Config) -> str:
    """Multi-line, human-oriented output for a terminal."""
    if not keyboards:
        return "zmkbat: no matching devices found (try --list)"

    lines: list[str] = []
    for keyboard in keyboards:
        status = "connected" if keyboard.connected else "not connected (asleep or off)"
        if keyboard.stale:
            status += f", cached {format_age(keyboard.age)} ago"
        lines.append(f"{keyboard.name}  [{keyboard.address}]  {status}")

        if keyboard.error and not keyboard.halves:
            lines.append(f"  ! {keyboard.error}")
            continue

        for half in keyboard.halves:
            name = _label(half, config)
            description = _describe(half)
            state = _state(half, keyboard, config)
            if state is HalfState.OFF:
                lines.append(f"  {name}{description:<{LABEL_WIDTH}} {'░' * BAR_WIDTH}  off")
                continue
            if state is HalfState.UNKNOWN:
                lines.append(f"  {name}{description:<{LABEL_WIDTH}} {'·' * BAR_WIDTH}   ?")
                continue
            note = ""
            if half.percent is not None and half.percent <= config.low:
                note = "  LOW"
            if state is HalfState.STALE:
                note += "  (cached)"
            lines.append(
                f"  {name}{description:<{LABEL_WIDTH}} "
                f"{format_bar(half.percent)} {half.percent:3d}%{note}"
            )

        if (
            keyboard.connected
            and len(keyboard.halves) == 1
            and keyboard.halves[0].role.value == "central"
        ):
            lines.append(
                "  (peripheral half is not published — is "
                "CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY enabled?)"
            )
        if keyboard.error:
            lines.append(f"  ! {keyboard.error}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# plain
# ---------------------------------------------------------------------------


def format_plain(keyboards: Sequence[Keyboard], config: Config) -> str:
    """Space-separated values, e.g. ``100 100``; ``off`` and ``?`` included."""
    values: list[str] = []
    for keyboard in keyboards:
        for half in keyboard.halves:
            state = _state(half, keyboard, config)
            if state is HalfState.OFF:
                values.append("off")
            elif state is HalfState.UNKNOWN:
                values.append("?")
            else:
                values.append(str(half.percent))
    return " ".join(values) if values else "?"


# ---------------------------------------------------------------------------
# polybar
# ---------------------------------------------------------------------------


def format_polybar(keyboards: Sequence[Keyboard], config: Config) -> str:
    """One line with polybar colour tags; stale data is dimmed and marked ``?``."""
    chunks: list[str] = []
    for keyboard in keyboards:
        parts: list[str] = []
        for half in keyboard.halves:
            name = _label(half, config)
            state = _state(half, keyboard, config)
            if state is HalfState.OFF:
                parts.append(f"{name} off")
                continue
            if state is HalfState.UNKNOWN:
                parts.append(f"{name} ?")
                continue
            icon = f"{battery_icon(half.percent)}" if config.icons else ""
            text = f"{name} {icon}{half.percent}%"
            if state is HalfState.STALE:
                parts.append(f"{text}?")
                continue
            if half.percent is not None and half.percent <= config.low:
                text = f"{CRITICAL}{text}{RESET}"
            elif half.percent is not None and half.percent <= config.low + 15:
                text = f"{WARNING}{text}{RESET}"
            parts.append(text)
        if not parts:
            continue
        line = " ".join(parts)
        if keyboard.stale:
            line = f"{DIM}{line}{RESET}"
        chunks.append(line)

    if not chunks:
        icon = f"{BLUETOOTH_ICON} " if config.icons else ""
        return f"{DIM}{icon}n/a{RESET}"
    prefix = f"{BLUETOOTH_ICON} " if config.icons else ""
    return prefix + " ".join(chunks)


# ---------------------------------------------------------------------------
# waybar
# ---------------------------------------------------------------------------


def format_waybar(keyboards: Sequence[Keyboard], config: Config) -> str:
    """A single JSON object with ``text``, ``tooltip`` and ``class``."""
    if not keyboards:
        return json.dumps(
            {
                "text": "n/a",
                "tooltip": "zmkbat: no matching devices found",
                "class": "offline",
            },
            ensure_ascii=False,
        )

    texts: list[str] = []
    tooltips: list[str] = []
    classes: list[str] = []
    for keyboard in keyboards:
        for half in keyboard.halves:
            name = _label(half, config)
            state = _state(half, keyboard, config)
            icon = battery_icon(half.percent) if config.icons else ""
            if state is HalfState.OFF:
                texts.append(f"{name} off")
            elif state is HalfState.UNKNOWN:
                texts.append(f"{name} ?")
            else:
                texts.append(f"{name} {icon}{half.percent}%")

            value = (
                state.value if state in (HalfState.OFF, HalfState.UNKNOWN) else f"{half.percent}%"
            )
            tooltip = f"{keyboard.name} [{keyboard.address}] {half.role.value}"
            if half.label:
                tooltip += f" ({half.label})"
            tooltip += f": {value}"
            if keyboard.stale:
                tooltip += f" (cached {format_age(keyboard.age)} ago)"
            tooltips.append(tooltip)

            if state in (HalfState.OFF, HalfState.UNKNOWN):
                classes.append("offline")
            elif half.percent is not None and half.percent <= config.low:
                classes.append("critical")
            elif half.percent is not None and half.percent <= config.low + 15:
                classes.append("warning")
            elif state is HalfState.STALE:
                classes.append("stale")
            else:
                classes.append("good")

    for candidate in ("critical", "warning", "offline", "stale", "good"):
        if candidate in classes:
            css_class = candidate
            break
    else:  # pragma: no cover - classes is never empty here
        css_class = "good"

    return json.dumps(
        {"text": " ".join(texts), "tooltip": "\n".join(tooltips), "class": css_class},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# json
# ---------------------------------------------------------------------------


def format_json(keyboards: Sequence[Keyboard], config: Config) -> str:
    """Machine-readable output for scripts."""
    payload = {
        "keyboards": [
            {
                "name": keyboard.name,
                "address": keyboard.address,
                "connected": keyboard.connected,
                "stale": keyboard.stale,
                "age": keyboard.age,
                "error": keyboard.error,
                "halves": [
                    {
                        "role": half.role.value,
                        "label": half.label,
                        "percent": half.percent,
                        "state": _state(half, keyboard, config).value,
                        "error": half.error,
                    }
                    for half in keyboard.halves
                ],
            }
            for keyboard in keyboards
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


FORMATTERS: dict[str, Callable[[Sequence[Keyboard], Config], str]] = {
    "text": format_text,
    "plain": format_plain,
    "polybar": format_polybar,
    "waybar": format_waybar,
    "json": format_json,
}


def format_output(fmt: str, keyboards: Sequence[Keyboard], config: Config) -> str:
    """Dispatch to the formatter named ``fmt``."""
    try:
        formatter = FORMATTERS[fmt]
    except KeyError as exc:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"unknown format: {fmt}") from exc
    return formatter(keyboards, config)
