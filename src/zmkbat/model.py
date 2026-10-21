"""Core data model shared by the BlueZ client, the cache and the formatters.

Keeping the model free of D-Bus and rendering concerns makes it trivial to
unit-test the interesting logic (state classification, minimum charge) without
a Bluetooth adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    """Which half of a split keyboard a reading belongs to.

    ``CENTRAL`` is the half that is connected to the host; ``PERIPHERAL`` is
    the other one, whose charge the central half proxies over its own GATT
    Battery Service.
    """

    CENTRAL = "central"
    PERIPHERAL = "peripheral"


class HalfState(str, Enum):
    """How much a reading can be trusted."""

    OK = "ok"
    """Fresh value read from a connected keyboard."""

    STALE = "stale"
    """Last known value from the cache; the keyboard is asleep or disconnected."""

    OFF = "off"
    """The peripheral half is not on the air (ZMK reports 0 for it)."""

    UNKNOWN = "unknown"
    """The characteristic could not be read at all."""


@dataclass(slots=True)
class Half:
    """A single battery reading for one half of the keyboard."""

    role: Role
    percent: int | None
    label: str = ""
    """Text of the 0x2901 descriptor, e.g. ``"Peripheral 0"``."""

    error: str | None = None


@dataclass(slots=True)
class Keyboard:
    """A Bluetooth device that exposes a ZMK Battery Service."""

    address: str
    name: str
    path: str
    connected: bool
    halves: list[Half] = field(default_factory=list)
    stale: bool = False
    age: int | None = None
    """Age of the cached data in seconds, when ``stale`` is true."""

    error: str | None = None

    def half(self, role: Role) -> Half | None:
        """Return the reading for ``role``, if present."""
        return next((half for half in self.halves if half.role is role), None)

    @property
    def min_percent(self) -> int | None:
        """Lowest known charge across both halves, or ``None``."""
        values = [half.percent for half in self.halves if half.percent is not None]
        return min(values) if values else None


def half_state(
    half: Half,
    keyboard: Keyboard,
    *,
    zero_means_off: bool = True,
) -> HalfState:
    """Classify a reading.

    ZMK reports ``0`` for the peripheral half when it disconnects: see
    ``split_central_disconnected()`` in ZMK's ``app/src/split/bluetooth/central.c``,
    which queues a battery event with ``level = 0``. Treating that zero as
    "0 % charge" would be wrong, so by default it means "the half is off".
    """
    if half.percent is None:
        return HalfState.UNKNOWN
    if half.role is Role.PERIPHERAL and half.percent == 0 and zero_means_off:
        return HalfState.OFF
    if keyboard.stale:
        return HalfState.STALE
    return HalfState.OK
