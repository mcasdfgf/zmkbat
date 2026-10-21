# Troubleshooting

## `no matching devices found`

```sh
zmkbat --list
```

The table lists every Bluetooth device BlueZ knows about. `*` marks the ones
that match the name pattern, `BAS` marks the ones that expose a Battery
Service.

* Keyboard missing entirely → it is not paired or not connected.
* Keyboard present but without `*` → give it a pattern:

  ```sh
  zmkbat --name-regex '(?i)myboard'
  ```

  or select by service instead of by name:

  ```sh
  zmkbat --any-battery
  ```

## Only one half is shown

The firmware does not publish the peripheral characteristic. Check the config:

```conf
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y
```

`text` mode prints a hint when it sees a single central reading.

## A half shows `?`

The characteristic exists but could not be read. Usually the peripheral half is
asleep or out of range. Try:

```sh
zmkbat --refresh -f json
```

If `error` is set on the half, the message comes straight from BlueZ.

## A half shows `off`

ZMK reports `0` for the peripheral when it disconnects. That is a deliberate
mapping, not a bug — see [how-it-works.md](how-it-works.md#4-classification).
If you want the literal value instead, set `"zero_means_off": false` in the
config.

## Values look frozen

They are probably cached. The cache lives in `~/.cache/zmkbat/state.json`:

```sh
zmkbat --refresh      # bypass a fresh cache entry
rm -rf ~/.cache/zmkbat  # drop it entirely
```

In `polybar` mode cached values are dimmed and end with `?`.

## The bar lags behind reality

`interval` in the bar and `--ttl` in the script decide how often a real
Bluetooth read happens. With `interval = 30` and the default TTL of 30 seconds
a change can take up to 30 seconds to appear. Lower both:

```ini
exec = zmkbat -f polybar -t 10
interval = 10
```

## `python3-dbus is not installed`

```sh
sudo dnf install python3-dbus        # Fedora
sudo apt install python3-dbus        # Debian/Ubuntu
sudo pacman -S python-dbus           # Arch
```

or, if you have the D-Bus headers:

```sh
pip install dbus-python
```

## `cannot talk to BlueZ`

The system bus is unreachable or `bluetoothd` is not running:

```sh
systemctl status bluetooth
busctl --system list | grep org.bluez
```

## Debugging

```sh
zmkbat --debug -f json
```

`--debug` enables debug logging and lets tracebacks through instead of turning
them into a one-line error.
