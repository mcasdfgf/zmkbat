"""Shared fixtures: keyboards, halves and a fake BlueZ client."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from zmkbat.bluez import DeviceInfo
from zmkbat.model import Half, Keyboard, Role

ADDRESS = "F9:8F:6F:00:00:00"
DEVICE_PATH = "/org/bluez/hci0/dev_F9_8F_6F_00_00_00"


@pytest.fixture
def keyboard_factory():
    """Build a :class:`Keyboard` with sensible defaults."""

    def make(
        halves: Iterable[Half],
        *,
        connected: bool = True,
        stale: bool = False,
        age: int | None = None,
        name: str = "EH K:03 v4",
        address: str = ADDRESS,
        error: str | None = None,
    ) -> Keyboard:
        return Keyboard(
            address=address,
            name=name,
            path=DEVICE_PATH,
            connected=connected,
            halves=list(halves),
            stale=stale,
            age=age,
            error=error,
        )

    return make


@pytest.fixture
def both_halves() -> list[Half]:
    return [Half(Role.CENTRAL, 100), Half(Role.PERIPHERAL, 100, "Peripheral 0")]


@pytest.fixture
def device_info() -> DeviceInfo:
    return DeviceInfo(
        path=DEVICE_PATH,
        address=ADDRESS,
        name="EH K:03 v4",
        connected=True,
        paired=True,
        services_resolved=True,
        has_battery_service=True,
        matches_name=True,
    )


class FakeClient:
    """A :class:`zmkbat.bluez.BluezClient` that never touches D-Bus."""

    def __init__(
        self,
        devices: Iterable[DeviceInfo] = (),
        halves: dict[str, list[Half]] | None = None,
        *,
        connect_result: bool = True,
    ) -> None:
        self._devices = list(devices)
        self._halves = halves or {}
        self.connect_result = connect_result
        self.reads = 0
        self.connects = 0

    def devices(self, name_regex: str, *, any_battery: bool = False, all_devices: bool = False):
        return list(self._devices)

    def read_halves(self, device_path: str) -> list[Half]:
        self.reads += 1
        return list(self._halves.get(device_path, []))

    def connect(self, device_path: str) -> bool:
        self.connects += 1
        return self.connect_result


@pytest.fixture
def fake_client_factory():
    """Return a factory that always yields the same :class:`FakeClient`."""

    def make(client: FakeClient):
        return lambda: client

    return make


@pytest.fixture(autouse=True)
def isolated_xdg(tmp_path, monkeypatch):
    """Keep config and cache out of the developer's home directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path
