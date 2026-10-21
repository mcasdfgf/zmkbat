"""Tests for every output format and every half state."""

from __future__ import annotations

import json

import pytest

from zmkbat.config import Config
from zmkbat.formatters import (
    format_age,
    format_bar,
    format_json,
    format_output,
    format_plain,
    format_polybar,
    format_text,
    format_waybar,
)
from zmkbat.model import Half, Role


@pytest.fixture
def config() -> Config:
    return Config()


def test_format_age_units():
    assert format_age(None) == "?"
    assert format_age(42) == "42s"
    assert format_age(420) == "7m"
    assert format_age(7200) == "2h"
    assert format_age(200000) == "2d"


def test_format_bar_edges():
    assert format_bar(None) == "·" * 10
    assert format_bar(0) == "░" * 10
    assert format_bar(100) == "█" * 10
    assert format_bar(50) == "█████░░░░░"


def test_text_both_halves(keyboard_factory, both_halves, config):
    output = format_text([keyboard_factory(both_halves)], config)
    assert "EH K:03 v4" in output
    assert "connected" in output
    assert "100%" in output
    assert "Peripheral 0" in output


def test_text_marks_low_battery(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 15), Half(Role.PERIPHERAL, 8, "Peripheral 0")])
    output = format_text([keyboard], config)
    assert output.count("LOW") == 2


def test_text_shows_off_for_disconnected_peripheral(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 100), Half(Role.PERIPHERAL, 0, "Peripheral 0")])
    output = format_text([keyboard], config)
    assert "R (Peripheral 0)" in output
    assert "off" in output
    assert "  0%" not in output


def test_text_hints_about_missing_proxy(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 87)])
    output = format_text([keyboard], config)
    assert "BATTERY_LEVEL_PROXY" in output


def test_text_marks_cached_values(keyboard_factory, both_halves, config):
    keyboard = keyboard_factory(both_halves, connected=False, stale=True, age=420)
    output = format_text([keyboard], config)
    assert "cached 7m ago" in output
    assert output.count("(cached)") == 2


def test_text_without_devices(config):
    assert "no matching devices" in format_text([], config)


def test_text_reports_errors(keyboard_factory, config):
    keyboard = keyboard_factory([], error="boom")
    assert "! boom" in format_text([keyboard], config)


def test_plain_output(keyboard_factory, both_halves, config):
    assert format_plain([keyboard_factory(both_halves)], config) == "100 100"


def test_plain_output_for_off_and_unknown(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, None), Half(Role.PERIPHERAL, 0)])
    assert format_plain([keyboard], config) == "? off"


def test_plain_output_without_devices(config):
    assert format_plain([], config) == "?"


def test_polybar_uses_icons_and_colours(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 15), Half(Role.PERIPHERAL, 8, "Peripheral 0")])
    output = format_polybar([keyboard], config)
    assert "%{F#bd2c40}" in output
    assert "L " in output and "R " in output


def test_polybar_warns_between_low_and_low_plus_15(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 30)])
    assert "%{F#FFAA01}" in format_polybar([keyboard], config)


def test_polybar_ascii_mode(keyboard_factory, both_halves):
    config = Config(icons=False)
    output = format_polybar([keyboard_factory(both_halves)], config)
    assert output == "L 100% R 100%"


def test_polybar_dims_stale_data(keyboard_factory, both_halves, config):
    keyboard = keyboard_factory(both_halves, connected=False, stale=True, age=60)
    output = format_polybar([keyboard], config)
    assert "%{F#555555}" in output
    assert output.endswith("%{F-}")
    assert output.count("?") == 2


def test_polybar_marks_off(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 100), Half(Role.PERIPHERAL, 0)])
    assert "R off" in format_polybar([keyboard], config)


def test_polybar_without_devices(config):
    assert "n/a" in format_polybar([], config)


def test_waybar_is_valid_json(keyboard_factory, both_halves, config):
    payload = json.loads(format_waybar([keyboard_factory(both_halves)], config))
    assert payload["class"] == "good"
    assert "L" in payload["text"] and "R" in payload["text"]
    assert "Peripheral 0" in payload["tooltip"]


def test_waybar_critical_class(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 5)])
    assert json.loads(format_waybar([keyboard], config))["class"] == "critical"


def test_waybar_offline_class(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 100), Half(Role.PERIPHERAL, 0)])
    assert json.loads(format_waybar([keyboard], config))["class"] == "offline"


def test_waybar_stale_class(keyboard_factory, both_halves, config):
    keyboard = keyboard_factory(both_halves, connected=False, stale=True, age=60)
    assert json.loads(format_waybar([keyboard], config))["class"] == "stale"


def test_waybar_without_devices(config):
    payload = json.loads(format_waybar([], config))
    assert payload["text"] == "n/a"
    assert payload["class"] == "offline"


def test_json_structure(keyboard_factory, both_halves, config):
    payload = json.loads(format_json([keyboard_factory(both_halves)], config))
    keyboard = payload["keyboards"][0]
    assert keyboard["address"] == "F9:8F:6F:00:00:00"
    assert [half["role"] for half in keyboard["halves"]] == ["central", "peripheral"]
    assert [half["state"] for half in keyboard["halves"]] == ["ok", "ok"]


def test_json_marks_off_state(keyboard_factory, config):
    keyboard = keyboard_factory([Half(Role.PERIPHERAL, 0)])
    payload = json.loads(format_json([keyboard], config))
    assert payload["keyboards"][0]["halves"][0]["state"] == "off"


def test_format_output_dispatch(keyboard_factory, both_halves, config):
    keyboards = [keyboard_factory(both_halves)]
    assert format_output("plain", keyboards, config) == "100 100"
    with pytest.raises(ValueError):
        format_output("nope", keyboards, config)
