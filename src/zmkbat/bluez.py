"""BlueZ access over D-Bus.

Only the pieces zmkbat needs are implemented:

* enumerate devices and their GATT objects via
  ``org.freedesktop.DBus.ObjectManager.GetManagedObjects``;
* read the Battery Level characteristic (``0x2A19``) of the Battery Service
  (``0x180F``) with ``org.bluez.GattCharacteristic1.ReadValue``;
* read the optional Characteristic User Description (``0x2901``) that ZMK adds
  to the proxied peripheral characteristic.

The parsing helpers (:func:`parse_devices`, :func:`battery_characteristics`)
are pure functions over the object tree returned by BlueZ, so they can be
tested without a Bluetooth adapter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .model import Half, Role

BLUEZ_SERVICE = "org.bluez"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
USER_DESCRIPTION_UUID = "00002901-0000-1000-8000-00805f9b34fb"

#: ``{object_path: {interface: {property: value}}}`` as returned by BlueZ.
ObjectTree = Mapping[str, Mapping[str, Mapping[str, Any]]]


class BluezError(RuntimeError):
    """Raised when BlueZ is unreachable or a GATT operation fails."""


@dataclass(slots=True)
class DeviceInfo:
    """A Bluetooth device known to BlueZ."""

    path: str
    address: str
    name: str
    connected: bool
    paired: bool
    services_resolved: bool
    has_battery_service: bool
    matches_name: bool


def parse_devices(
    objects: ObjectTree,
    name_regex: str,
    *,
    any_battery: bool = False,
    all_devices: bool = False,
) -> list[DeviceInfo]:
    """Extract devices from a BlueZ object tree.

    By default a device is selected when its name matches ``name_regex``.
    With ``any_battery`` any device exposing the Battery Service is selected
    instead, and with ``all_devices`` nothing is filtered out (used by
    ``--list``). Connected devices come first.
    """
    pattern = re.compile(name_regex)
    devices: list[DeviceInfo] = []
    for path, interfaces in objects.items():
        properties = interfaces.get("org.bluez.Device1")
        if not properties:
            continue
        uuids = {str(uuid).lower() for uuid in properties.get("UUIDs", [])}
        name = str(properties.get("Alias") or properties.get("Name") or "")
        has_battery_service = BATTERY_SERVICE_UUID in uuids
        matches_name = bool(pattern.search(name))
        if not all_devices:
            if any_battery and not has_battery_service:
                continue
            if not any_battery and not matches_name:
                continue
        devices.append(
            DeviceInfo(
                path=path,
                address=str(properties.get("Address", "")),
                name=name,
                connected=bool(properties.get("Connected", False)),
                paired=bool(properties.get("Paired", False)),
                services_resolved=bool(properties.get("ServicesResolved", False)),
                has_battery_service=has_battery_service,
                matches_name=matches_name,
            )
        )
    devices.sort(key=lambda device: (not device.connected, device.name.lower()))
    return devices


def battery_characteristics(objects: ObjectTree, device_path: str) -> list[tuple[str, str | None]]:
    """Return ``(characteristic_path, user_description_path)`` pairs.

    A ZMK central half publishes one Battery Level characteristic for itself
    and, when ``CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY`` is enabled,
    one more for the peripheral half. The proxied one carries a ``0x2901``
    descriptor whose text is ``"Peripheral 0"``; the central one does not.
    """
    services = [
        path
        for path, interfaces in objects.items()
        if "org.bluez.GattService1" in interfaces
        and str(interfaces["org.bluez.GattService1"].get("Device", "")) == device_path
        and str(interfaces["org.bluez.GattService1"].get("UUID", "")).lower()
        == BATTERY_SERVICE_UUID
    ]

    pairs: list[tuple[str, str | None]] = []
    for service in services:
        for path, interfaces in objects.items():
            characteristic = interfaces.get("org.bluez.GattCharacteristic1")
            if not characteristic:
                continue
            if str(characteristic.get("Service", "")) != service:
                continue
            if str(characteristic.get("UUID", "")).lower() != BATTERY_LEVEL_UUID:
                continue
            pairs.append((path, _user_description(objects, path)))
    return pairs


def _user_description(objects: ObjectTree, characteristic_path: str) -> str | None:
    for path, interfaces in objects.items():
        descriptor = interfaces.get("org.bluez.GattDescriptor1")
        if not descriptor:
            continue
        if str(descriptor.get("Characteristic", "")) != characteristic_path:
            continue
        if str(descriptor.get("UUID", "")).lower() == USER_DESCRIPTION_UUID:
            return path
    return None


class BluezClient(Protocol):
    """The subset of BlueZ behaviour the rest of the code depends on."""

    def devices(
        self,
        name_regex: str,
        *,
        any_battery: bool = False,
        all_devices: bool = False,
    ) -> list[DeviceInfo]: ...

    def read_halves(self, device_path: str) -> list[Half]: ...

    def connect(self, device_path: str) -> bool: ...


class DbusBluezClient:
    """A :class:`BluezClient` backed by ``dbus-python`` and the system bus."""

    def __init__(self, bus: Any | None = None) -> None:
        try:
            import dbus
        except ImportError as exc:  # pragma: no cover - depends on the system
            raise BluezError(
                "python3-dbus is not installed; install it with your package manager "
                "(e.g. 'sudo dnf install python3-dbus') or 'pip install dbus-python'"
            ) from exc
        self._dbus = dbus
        self._bus = bus if bus is not None else dbus.SystemBus()
        self._manager = dbus.Interface(
            self._bus.get_object(BLUEZ_SERVICE, "/"),
            "org.freedesktop.DBus.ObjectManager",
        )

    # -- BluezClient -------------------------------------------------------

    def devices(
        self,
        name_regex: str,
        *,
        any_battery: bool = False,
        all_devices: bool = False,
    ) -> list[DeviceInfo]:
        return parse_devices(
            self._objects(),
            name_regex,
            any_battery=any_battery,
            all_devices=all_devices,
        )

    def read_halves(self, device_path: str) -> list[Half]:
        objects = self._objects()
        halves: list[Half] = []
        for characteristic_path, description_path in battery_characteristics(objects, device_path):
            role = Role.PERIPHERAL if description_path else Role.CENTRAL
            if any(half.role is role for half in halves):
                # Non-standard firmware: fall back to the free role.
                role = Role.CENTRAL if role is Role.PERIPHERAL else Role.PERIPHERAL
            label = self._read_text(description_path) if description_path else ""
            percent = self._read_byte(characteristic_path)
            halves.append(
                Half(
                    role=role,
                    percent=percent,
                    label=label,
                    error=None if percent is not None else "read failed",
                )
            )
        halves.sort(key=lambda half: 0 if half.role is Role.CENTRAL else 1)
        return halves

    def connect(self, device_path: str) -> bool:
        try:
            device = self._dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, device_path), "org.bluez.Device1"
            )
            device.Connect()
        except self._dbus.DBusException:
            return False
        return True

    # -- internals ---------------------------------------------------------

    def _objects(self) -> ObjectTree:
        try:
            return self._manager.GetManagedObjects()
        except self._dbus.DBusException as exc:
            raise BluezError(f"cannot talk to BlueZ: {exc.get_dbus_message()}") from exc

    def _read_byte(self, path: str) -> int | None:
        """Read a one-byte characteristic, falling back to its cached value."""
        try:
            characteristic = self._dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path),
                "org.bluez.GattCharacteristic1",
            )
            value = characteristic.ReadValue({})
            if len(value) >= 1:
                return int(value[0])
        except self._dbus.DBusException:
            pass
        try:
            properties = self._dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path),
                "org.freedesktop.DBus.Properties",
            )
            value = properties.Get("org.bluez.GattCharacteristic1", "Value")
            if len(value) >= 1:
                return int(value[0])
        except self._dbus.DBusException:
            pass
        return None

    def _read_text(self, path: str) -> str:
        try:
            descriptor = self._dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, path), "org.bluez.GattDescriptor1"
            )
            raw = bytes(bytearray(descriptor.ReadValue({})))
        except self._dbus.DBusException:
            return ""
        return raw.decode("utf-8", "replace").strip("\x00").strip()


def describe_devices(devices: Sequence[DeviceInfo]) -> str:
    """Human-readable table used by ``zmkbat --list``."""
    header = f"{'ADDRESS':<17}  {'NAME':<24}  {'STATE':<12}  BAS  MATCH"
    rows = [header]
    for device in devices:
        rows.append(
            f"{device.address:<17}  {device.name[:24]:<24}  "
            f"{'connected' if device.connected else 'disconnected':<12}  "
            f"{'yes' if device.has_battery_service else ' - ':<3}  "
            f"{'*' if device.matches_name else ''}"
        )
    return "\n".join(rows)
