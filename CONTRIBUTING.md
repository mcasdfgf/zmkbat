# Contributing

Thanks for taking a look. This is a small tool, so the process is small too.

## Getting started

```sh
git clone https://github.com/mcasdfgf/zmkbat.git
cd zmkbat
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

`dbus-python` needs the D-Bus and GLib headers to build:

```sh
sudo dnf install dbus-devel glib2-devel                          # Fedora
sudo apt install libdbus-1-dev libglib2.0-dev pkg-config         # Debian/Ubuntu
```

If you already have the distribution's `python3-dbus`, create the virtualenv
with `--system-site-packages` and install with `pip install -e .` instead.

## Before opening a pull request

```sh
make lint    # ruff check + ruff format --check
make test    # pytest
```

Both must pass. CI runs the same commands on Python 3.10 through 3.13.

## Code style

* Python 3.10+, `from __future__ import annotations` everywhere.
* Type hints on public functions; `dataclass(slots=True)` for data holders.
* Comments and docstrings in English, explaining *why*, not *what*.
* Keep the D-Bus layer in `bluez.py` and the rendering in `formatters.py`.
  Anything that can be a pure function should be one — that is what makes the
  test suite run without a keyboard.
* No new runtime dependencies without a good reason. `dbus-python` is the only
  one, and it is a system package on every distribution.

## Tests

The suite must not require a Bluetooth adapter or a running BlueZ. Use the
`FakeClient` from `tests/conftest.py` and the object trees in
`tests/test_bluez.py` as templates.

If you add a new output format, add it to `FORMATTERS`, to the `--format`
choices and to `tests/test_formatters.py`.

## Commit messages

Conventional Commits, please:

```
feat: add a waybar return-type json snippet
fix: treat a zero from the peripheral as off
docs: explain the 0x2901 heuristic
test: cover the stale cache path
```

## Reporting bugs

Include:

* `zmkbat --version`;
* `zmkbat --list` output;
* `zmkbat --debug -f json` output;
* your keyboard model and the relevant `CONFIG_ZMK_*` options.

Please redact Bluetooth addresses if you care about them.
