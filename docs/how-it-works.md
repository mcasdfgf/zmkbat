# How zmkbat works

This document walks through the whole path: from the GATT attributes a ZMK
keyboard exposes, through the BlueZ D-Bus objects, to the state a formatter
prints.

## 1. What ZMK exposes

ZMK implements the standard Bluetooth SIG Battery Service:

```
service 0x180F (Battery Service)
└── characteristic 0x2A19 (Battery Level)   uint8, 0..100
    ├── descriptor 0x2902 (CCCD)            notifications
    └── descriptor 0x2904 (Presentation Format)
```

On a split keyboard the central half is the one connected to the host. With

```conf
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y
```

the central half publishes a **second** Battery Service containing a second
`0x2A19` characteristic, which reports the peripheral half's charge. That
characteristic additionally carries a Characteristic User Description
(`0x2901`) whose value is the string `Peripheral 0`:

```
service 0x180F (central half)
└── characteristic 0x2A19                  <- central charge
    ├── descriptor 0x2902
    └── descriptor 0x2904

service 0x180F (proxied peripheral)
└── characteristic 0x2A19                  <- peripheral charge
    ├── descriptor 0x2902
    ├── descriptor 0x2904
    └── descriptor 0x2901 = "Peripheral 0"
```

The presence of `0x2901` is the only reliable difference between the two
characteristics, and it is exactly what
[zmkBATx](https://github.com/mh4x0f/zmkBATx) uses. `zmkbat` does the same.

## 2. What BlueZ exposes

BlueZ mirrors the GATT tree as D-Bus objects under the device path:

```
/org/bluez/hci0/dev_F9_8F_6F_00_00_00
├── org.bluez.Device1
├── /service0010
│   ├── org.bluez.GattService1        UUID=0000180f-...
│   └── /char0011
│       ├── org.bluez.GattCharacteristic1  UUID=00002a19-...
│       ├── /desc0013  org.bluez.GattDescriptor1  UUID=00002902-...
│       └── /desc0014  org.bluez.GattDescriptor1  UUID=00002904-...
└── /service0015
    ├── org.bluez.GattService1        UUID=0000180f-...
    └── /char0016
        ├── org.bluez.GattCharacteristic1  UUID=00002a19-...
        ├── /desc0018  org.bluez.GattDescriptor1  UUID=00002902-...
        ├── /desc0019  org.bluez.GattDescriptor1  UUID=00002904-...
        └── /desc001a  org.bluez.GattDescriptor1  UUID=00002901-...  <- "Peripheral 0"
```

Everything is readable by an unprivileged user; no `sudo`, no `bluetoothctl`
session, no pairing agent.

## 3. The calls zmkbat makes

| call | purpose |
|---|---|
| `org.freedesktop.DBus.ObjectManager.GetManagedObjects` on `/` | one snapshot of every device, service, characteristic and descriptor |
| `org.bluez.GattCharacteristic1.ReadValue({})` | fresh BLE read of `0x2A19` |
| `org.bluez.GattDescriptor1.ReadValue({})` | text of `0x2901`, used as the half's label |
| `org.bluez.Device1.Connect()` | only with `--connect` |

`ReadValue` performs an actual GATT read. If it fails (the device is busy or
just went to sleep), `zmkbat` falls back to the cached `Value` property, and
then to the on-disk cache.

The parsing itself is pure: `parse_devices()` and `battery_characteristics()`
take the object tree as a plain mapping, which is why the test suite can cover
them without a Bluetooth adapter.

## 4. Classification

Each reading becomes a `Half` with a `Role` (`central` or `peripheral`) and a
`HalfState`:

| state | when | rendered as |
|---|---|---|
| `ok` | fresh value from a connected keyboard | `L 87%` |
| `stale` | value from the cache, keyboard asleep/disconnected | `L 87%?` (dimmed) |
| `off` | peripheral reports `0` | `R off` |
| `unknown` | characteristic could not be read | `R ?` |

`off` deserves a note. When the peripheral half disconnects, ZMK queues a
battery event with `level = 0`:

```c
/* zmk/app/src/split/bluetooth/central.c */
static void split_central_disconnected(struct bt_conn *conn, uint8_t reason) {
    ...
#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING)
    struct peripheral_event_wrapper ev = {
        .source = peripheral_slot_index_for_conn(conn),
        .event = {.type = ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_BATTERY_EVENT,
                  .data = {.battery_event = {.level = 0}}}};
    ...
#endif
}
```

So a zero from the peripheral means "not on the air". Treating it as "0 %
charge" would light up the bar in red every time you switch the right half off.
`zero_means_off: false` in the config restores the literal behaviour.

## 5. Cache and TTL

A status bar asks its script every few seconds; a battery level changes every
few hours. Every `ReadValue` is a Bluetooth round trip, so `zmkbat` keeps the
last readings in `~/.cache/zmkbat/state.json`:

* if the entry is younger than `ttl` and the keyboard is connected, the cache
  answers and no BLE traffic happens;
* otherwise the characteristics are read and the entry is rewritten;
* if the keyboard is disconnected, the entry is served with `stale = true`.

The file is written atomically (`state.tmp` + `os.replace`), carries a schema
version, and is ignored if it is corrupt or from a future version. A read-only
cache directory is not fatal.

## 6. Exit codes

`run_once()` reduces the readings to one of three codes:

* `0` — at least one usable reading, all above `--low`;
* `1` — no devices, or no usable readings at all;
* `2` — at least one usable reading at or below `--low`.

`off` and `unknown` readings never trigger `2`: a switched-off half is not a
low battery.
