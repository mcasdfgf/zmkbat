"""Tests for the pure parsing helpers in :mod:`zmkbat.bluez`.

The object trees below mirror what BlueZ returns for a real ZMK keyboard
(an EH K:03 v4), so the tests exercise the same shapes as production.
"""

from __future__ import annotations

from zmkbat.bluez import (
    BATTERY_LEVEL_UUID,
    BATTERY_SERVICE_UUID,
    USER_DESCRIPTION_UUID,
    battery_characteristics,
    describe_devices,
    parse_devices,
)

DEVICE = "/org/bluez/hci0/dev_F9_8F_6F_00_00_00"
BAS_CENTRAL = f"{DEVICE}/service0010"
BAS_PERIPHERAL = f"{DEVICE}/service0015"
CHAR_CENTRAL = f"{BAS_CENTRAL}/char0011"
CHAR_PERIPHERAL = f"{BAS_PERIPHERAL}/char0016"
CCCD = "00002902-0000-1000-8000-00805f9b34fb"


def device_properties(**overrides):
    properties = {
        "Address": "F9:8F:6F:00:00:00",
        "Alias": "EH K:03 v4",
        "Connected": True,
        "Paired": True,
        "ServicesResolved": True,
        "UUIDs": [BATTERY_SERVICE_UUID],
    }
    properties.update(overrides)
    return properties


def object_tree(*, with_peripheral: bool = True, **device_overrides):
    tree = {
        "/org/bluez/hci0": {"org.bluez.Adapter1": {"Address": "B8:FB:B3:FA:15:95"}},
        DEVICE: {"org.bluez.Device1": device_properties(**device_overrides)},
        BAS_CENTRAL: {"org.bluez.GattService1": {"Device": DEVICE, "UUID": BATTERY_SERVICE_UUID}},
        CHAR_CENTRAL: {
            "org.bluez.GattCharacteristic1": {
                "Service": BAS_CENTRAL,
                "UUID": BATTERY_LEVEL_UUID,
            }
        },
        f"{CHAR_CENTRAL}/desc0013": {
            "org.bluez.GattDescriptor1": {"Characteristic": CHAR_CENTRAL, "UUID": CCCD}
        },
    }
    if with_peripheral:
        tree[BAS_PERIPHERAL] = {
            "org.bluez.GattService1": {"Device": DEVICE, "UUID": BATTERY_SERVICE_UUID}
        }
        tree[CHAR_PERIPHERAL] = {
            "org.bluez.GattCharacteristic1": {
                "Service": BAS_PERIPHERAL,
                "UUID": BATTERY_LEVEL_UUID,
            }
        }
        tree[f"{CHAR_PERIPHERAL}/desc001a"] = {
            "org.bluez.GattDescriptor1": {
                "Characteristic": CHAR_PERIPHERAL,
                "UUID": USER_DESCRIPTION_UUID,
            }
        }
    return tree


# -- parse_devices ---------------------------------------------------------


def test_parse_devices_matches_by_name():
    devices = parse_devices(object_tree(), r"(?i)k:0")
    assert len(devices) == 1
    assert devices[0].address == "F9:8F:6F:00:00:00"
    assert devices[0].matches_name is True
    assert devices[0].has_battery_service is True


def test_parse_devices_skips_non_matching_names():
    assert parse_devices(object_tree(), r"corne") == []


def test_parse_devices_any_battery_ignores_the_name():
    devices = parse_devices(object_tree(), r"corne", any_battery=True)
    assert len(devices) == 1


def test_parse_devices_any_battery_requires_the_service():
    tree = object_tree(UUIDs=[])
    assert parse_devices(tree, r"corne", any_battery=True) == []


def test_parse_devices_all_devices_keeps_everything():
    tree = object_tree(UUIDs=[])
    devices = parse_devices(tree, r"corne", all_devices=True)
    assert len(devices) == 1
    assert devices[0].matches_name is False


def test_parse_devices_ignores_objects_without_device1():
    tree = object_tree()
    tree["/org/bluez/hci0/service0001"] = {"org.bluez.GattService1": {"UUID": "x"}}
    assert len(parse_devices(tree, r"(?i)k:0")) == 1


def test_parse_devices_sorts_connected_first():
    tree = object_tree()
    tree["/org/bluez/hci0/dev_AA"] = {
        "org.bluez.Device1": device_properties(
            Address="AA:BB:CC:DD:EE:FF", Alias="zmk asleep", Connected=False
        )
    }
    devices = parse_devices(tree, r"(?i)(k:0|zmk)")
    assert [device.connected for device in devices] == [True, False]


def test_parse_devices_uses_name_when_alias_is_missing():
    tree = object_tree(Alias="", Name="Corne")
    devices = parse_devices(tree, r"(?i)corne")
    assert devices[0].name == "Corne"


# -- battery_characteristics ----------------------------------------------


def test_battery_characteristics_finds_both_halves():
    pairs = battery_characteristics(object_tree(), DEVICE)
    assert pairs == [(CHAR_CENTRAL, None), (CHAR_PERIPHERAL, f"{CHAR_PERIPHERAL}/desc001a")]


def test_battery_characteristics_without_proxy():
    pairs = battery_characteristics(object_tree(with_peripheral=False), DEVICE)
    assert pairs == [(CHAR_CENTRAL, None)]


def test_battery_characteristics_ignores_other_devices():
    assert battery_characteristics(object_tree(), "/org/bluez/hci0/dev_OTHER") == []


def test_battery_characteristics_ignores_other_services():
    tree = object_tree()
    tree["/org/bluez/hci0/dev_F9_8F_6F_00_00_00/service0099"] = {
        "org.bluez.GattService1": {"Device": DEVICE, "UUID": "00001812-0000-1000-8000-00805f9b34fb"}
    }
    tree["/org/bluez/hci0/dev_F9_8F_6F_00_00_00/service0099/char009a"] = {
        "org.bluez.GattCharacteristic1": {
            "Service": "/org/bluez/hci0/dev_F9_8F_6F_00_00_00/service0099",
            "UUID": BATTERY_LEVEL_UUID,
        }
    }
    assert len(battery_characteristics(tree, DEVICE)) == 2


# -- describe_devices ------------------------------------------------------


def test_describe_devices_renders_a_table():
    devices = parse_devices(object_tree(), r"(?i)k:0")
    table = describe_devices(devices)
    lines = table.splitlines()
    assert lines[0].startswith("ADDRESS")
    assert "F9:8F:6F:00:00:00" in lines[1]
    assert lines[1].rstrip().endswith("*")
