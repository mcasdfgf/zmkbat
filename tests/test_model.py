"""Tests for the state classification in :mod:`zmkbat.model`."""

from __future__ import annotations

from zmkbat.model import Half, HalfState, Role, half_state


def test_unknown_when_percent_is_missing(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, None)])
    assert half_state(keyboard.halves[0], keyboard) is HalfState.UNKNOWN


def test_ok_for_a_fresh_reading(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 87)])
    assert half_state(keyboard.halves[0], keyboard) is HalfState.OK


def test_zero_from_peripheral_means_off(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.PERIPHERAL, 0, "Peripheral 0")])
    assert half_state(keyboard.halves[0], keyboard) is HalfState.OFF


def test_zero_from_peripheral_can_be_a_real_value(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.PERIPHERAL, 0, "Peripheral 0")])
    assert half_state(keyboard.halves[0], keyboard, zero_means_off=False) is HalfState.OK


def test_zero_from_central_is_not_off(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 0)])
    assert half_state(keyboard.halves[0], keyboard) is HalfState.OK


def test_cached_reading_is_stale(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 64)], connected=False, stale=True, age=420)
    assert half_state(keyboard.halves[0], keyboard) is HalfState.STALE


def test_off_wins_over_stale(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.PERIPHERAL, 0)], stale=True, age=10)
    assert half_state(keyboard.halves[0], keyboard) is HalfState.OFF


def test_min_percent_ignores_unknown_values(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 80), Half(Role.PERIPHERAL, None)])
    assert keyboard.min_percent == 80


def test_min_percent_is_none_without_readings(keyboard_factory):
    assert keyboard_factory([]).min_percent is None


def test_half_lookup_by_role(keyboard_factory):
    keyboard = keyboard_factory([Half(Role.CENTRAL, 80), Half(Role.PERIPHERAL, 70)])
    assert keyboard.half(Role.PERIPHERAL).percent == 70
    assert keyboard.half(Role.CENTRAL).percent == 80
