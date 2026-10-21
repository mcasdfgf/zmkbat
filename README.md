# zmkbat

[![CI](https://github.com/mcasdfgf/zmkbat/actions/workflows/ci.yml/badge.svg)](https://github.com/mcasdfgf/zmkbat/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

> [!WARNING]
> **This project is AI-generated.** The repository, its code, tests and
> documentation were written and are maintained with the help of an AI
> assistant. It is published as-is, with no warranty of any kind: read the
> code before you rely on it, and use it at your own risk. See [LICENSE](LICENSE).

Battery levels for **both halves** of a ZMK split keyboard, in the console.

No tray icon, no Qt, no root. One command that prints something a status bar
can use, and a JSON mode for everything else.

```
$ zmkbat
EH K:03 v4  [F9:8F:6F:47:37:0A]  connected
  L                   ██████████ 100%
  R (Peripheral 0)    ██████████ 100%

$ zmkbat -f polybar
󰂯 L 󰁹100% R 󰁹100%
```

---

## Why this exists

ZMK split keyboards report the charge of the half that is connected to the
host. The other half's charge is proxied through the central half, and most
desktop tools only show the first value they find — so you see one number and
have to guess which half it belongs to.

[zmkBATx](https://github.com/mh4x0f/zmkBATx) solves this properly, but it is a
Qt application with a tray icon. On a tiling setup (i3, sway, Hyprland) there
is no tray to look at, and pulling in Qt6 + a C++ build to read two bytes over
Bluetooth is a lot of machinery.

`zmkbat` is the same idea reduced to what a status bar actually needs:

* **both halves**, clearly labelled, with the peripheral half detected the same
  way zmkBATx does it;
* **one line of output** for polybar/waybar/i3blocks, plus `text`, `plain` and
  `json` for everything else;
* **a cache with a TTL**, so a bar polling every few seconds does not turn into
  a Bluetooth round trip every few seconds;
* **honest states**: `off` when a half is not on the air, `?` when a value
  cannot be read, dimmed values when they come from the cache;
* **exit codes** that map onto i3blocks' colouring (`2` = low battery).

## Prior art and inspiration

* [zmkBATx](https://github.com/mh4x0f/zmkBATx) — the original tool this project
  is modelled after. The peripheral-detection trick (the `0x2901` descriptor)
  comes from there.
* [ZMK battery documentation](https://zmk.dev/docs/config/battery) — describes
  `CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY` and
  `..._FETCHING`, which make the second characteristic appear at all.
* [BlueZ](https://www.bluez.org/) — the D-Bus API that exposes GATT to
  unprivileged users.

## How it works

ZMK publishes charge through the standard GATT Battery Service (`0x180F`).
With the proxy options enabled, the central half exposes **two** Battery Level
characteristics (`0x2A19`): its own and the peripheral's. The peripheral one
carries a Characteristic User Description (`0x2901`) whose text is
`Peripheral 0`; the central one does not. That single descriptor is what tells
the halves apart.

`zmkbat` reads the object tree from BlueZ over D-Bus, finds those
characteristics, reads them and classifies the result. The full walkthrough,
including the exact D-Bus calls and the state machine, is in
[docs/how-it-works.md](docs/how-it-works.md).

## Requirements

* Linux with BlueZ (any recent version; tested with 5.87);
* Python 3.10 or newer;
* `python3-dbus` — a system package on every distribution, or
  `pip install 'zmkbat[dbus]'` if you have the D-Bus and GLib headers;
* a ZMK keyboard with:

  ```conf
  CONFIG_ZMK_BATTERY_REPORTING=y
  CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
  CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y
  ```

  Without the two split options only the central half is visible.

## Installation

`zmkbat` talks to BlueZ through `dbus-python`, which every Linux distribution
ships as a system package. Install that first:

```sh
sudo dnf install python3-dbus        # Fedora
sudo apt install python3-dbus        # Debian/Ubuntu
sudo pacman -S python-dbus           # Arch
```

Then install the tool. With pipx, let it see the system packages so it can use
the distribution's `dbus-python`:

```sh
pipx install --system-site-packages zmkbat
```

From a checkout (recommended while the project is young):

```sh
git clone https://github.com/mcasdfgf/zmkbat.git
cd zmkbat
pipx install --system-site-packages .
```

If you prefer a fully isolated environment, build `dbus-python` inside it —
that needs the D-Bus and GLib headers:

```sh
sudo dnf install dbus-devel glib2-devel          # Fedora
sudo apt install libdbus-1-dev libglib2.0-dev pkg-config
pipx install 'zmkbat[dbus]'
```

Or run it without installing anything:

```sh
./bin/zmkbat --list
```

## Quick start

```sh
zmkbat --list     # every Bluetooth device; '*' marks the ones that match
zmkbat            # human-readable output
zmkbat -f polybar # one line for the bar
```

If your keyboard is not marked with `*`, give it a name pattern:

```sh
zmkbat --name-regex '(?i)myboard'
# or select anything that exposes a Battery Service:
zmkbat --any-battery
```

## Usage

```
zmkbat [-f FORMAT] [-d DEVICE] [-l LOW] [-t TTL] [-w [SEC]]
       [--list] [--connect] [--ascii] [--name-regex REGEX] [--any-battery]
       [--no-cache] [--refresh] [--debug] [--version]
```

| option | meaning |
|---|---|
| `-f, --format` | `text` (default), `plain`, `polybar`, `waybar`, `json` |
| `-d, --device` | address or name substring, e.g. `-d k:03` |
| `-l, --low` | low battery threshold in percent (default `20`) |
| `-t, --ttl` | how long a cached reading stays fresh, seconds (default `30`) |
| `-w, --watch [SEC]` | refresh continuously (default `5` seconds) |
| `--list` | list Bluetooth devices and exit |
| `--connect` | try to connect a disconnected keyboard |
| `--ascii` | no Nerd Font icons |
| `--name-regex` | regular expression for device names |
| `--any-battery` | select devices by Battery Service instead of by name |
| `--no-cache` | neither read nor write the cache |
| `--refresh` | ignore a fresh cache entry and read again |
| `--debug` | debug logging and tracebacks |

### Exit codes

| code | meaning |
|---|---|
| `0` | everything is fine |
| `1` | no device, or no readable values |
| `2` | at least one half is at or below `--low` |

i3blocks maps `2` to its `critical` colour automatically.

### Formats

```sh
$ zmkbat -f text
EH K:03 v4  [F9:8F:6F:47:37:0A]  connected
  L                   ██████████ 100%
  R (Peripheral 0)    ██████████ 100%

$ zmkbat -f plain
100 100

$ zmkbat -f polybar
󰂯 L 󰁹100% R 󰁹100%

$ zmkbat -f waybar
{"text": "L 󰁹100% R 󰁹100%", "tooltip": "...", "class": "good"}

$ zmkbat -f json
{
  "keyboards": [
    {
      "name": "EH K:03 v4",
      "address": "F9:8F:6F:47:37:0A",
      "connected": true,
      "stale": false,
      "halves": [
        {"role": "central", "percent": 100, "state": "ok"},
        {"role": "peripheral", "label": "Peripheral 0", "percent": 100, "state": "ok"}
      ]
    }
  ]
}
```

In `polybar` mode the colour follows the charge: red at or below `--low`,
orange up to `--low + 15`. Cached values are dimmed and suffixed with `?`.

## Status bar integration

Ready-to-paste snippets live in [`contrib/`](contrib):

* [polybar](contrib/polybar.ini) — `interval = 10`, left click opens the
  detailed view in rofi, right click forces a refresh;
* [waybar](contrib/waybar.jsonc) — `custom/script` with `return-type: json`;
* [i3blocks](contrib/i3blocks.conf) — `interval = 30`, exit code `2` colours
  the block.

A minimal polybar module:

```ini
[module/zmkbat]
type = custom/script
exec = zmkbat -f polybar -t 10
interval = 10
format-prefix = "KB "
label = %output%
click-left = zmkbat --refresh -f text | rofi -dmenu -p battery -no-custom
```

`interval` and `--ttl` should match: the bar asks every 10 seconds, the cache
answers for 10 seconds, so a real Bluetooth read happens once per 10 seconds
per bar. Two bars on two monitors still share one read.

## Configuration

Optional file at `~/.config/zmkbat/config.json` (or
`$XDG_CONFIG_HOME/zmkbat/config.json`). Command line options win.

```json
{
  "device": null,
  "name_regex": "(?i)(zmk|ergohaven|\\bEH\\b|k:0|corne|sofle)",
  "ttl": 30,
  "low": 20,
  "format": "text",
  "icons": true,
  "labels": { "central": "L", "peripheral": "R" },
  "connect": false,
  "zero_means_off": true,
  "any_battery": false
}
```

`labels` controls how the halves are named. If your central half is the right
one, swap them: `{"central": "R", "peripheral": "L"}`.

Unknown keys are rejected on purpose — a typo in a config file should be
visible, not silently ignored.

## Edge cases

| situation | what you get |
|---|---|
| both halves on the air | `L 100% R 100%` |
| peripheral half switched off | `L 100% R off` (dimmed), exit code `0` |
| firmware without the proxy options | only `L 87%`, plus a hint in `text` mode |
| keyboard asleep or disconnected, cache present | cached values, `cached 7m ago` in `text`, dimmed `?` in `polybar` |
| keyboard asleep, no cache | `n/a`, exit code `1` |
| characteristic unreadable | `?`, exit code `1` |
| several split keyboards | all matching devices, one after another |

### Why `off` and not `0%`

When the peripheral half disconnects, ZMK queues a battery event with
`level = 0` (see `split_central_disconnected()` in ZMK's
`app/src/split/bluetooth/central.c`). A zero from the peripheral therefore
means "not on the air", not "empty". `zero_means_off: false` restores the
literal reading if you prefer it.

### Sleep

With `CONFIG_ZMK_SLEEP=y` both halves fall asleep after the idle timeout and
the Bluetooth link to the host drops. `zmkbat` sees `Connected=false`, serves
the cache and marks it as stale. After a key press the keyboard reconnects and
the next tick shows fresh values. If the GATT tree is not resolved yet, the
tool says so instead of inventing numbers.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md). The short version:

```sh
zmkbat --list                 # is the keyboard there at all?
zmkbat --refresh -f json      # what exactly is being read?
zmkbat --debug                # what is BlueZ saying?
```

## Development

```sh
make test     # pytest
make lint     # ruff check + ruff format --check
make fmt      # ruff format + ruff check --fix
make run      # ./bin/zmkbat
```

Layout:

```
src/zmkbat/
  bluez.py       BlueZ D-Bus access + pure parsing helpers
  cache.py       JSON cache with TTL and atomic writes
  cli.py         argument parsing, collection, exit codes
  config.py      config file loading and validation
  formatters.py  text / plain / polybar / waybar / json
  icons.py       Nerd Font glyphs
  model.py       Half, Keyboard, state classification
tests/           pytest suite, no Bluetooth adapter required
contrib/         status bar snippets
docs/            protocol walkthrough and troubleshooting
```

The test suite never touches D-Bus: the parsing helpers are pure functions and
the CLI accepts a client factory, so a fake client is enough.

## License

MIT — see [LICENSE](LICENSE).
