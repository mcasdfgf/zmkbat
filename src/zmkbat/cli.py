"""Command line interface.

The CLI is deliberately thin: it parses arguments, merges them with the config
file, asks :mod:`zmkbat.bluez` for readings, stores them in the cache and hands
everything to :mod:`zmkbat.formatters`.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from enum import IntEnum

from . import __version__
from .bluez import BluezClient, BluezError, DbusBluezClient, describe_devices
from .cache import Cache
from .config import OUTPUT_FORMATS, Config, ConfigError
from .formatters import format_output
from .model import HalfState, Keyboard, half_state

LOG = logging.getLogger("zmkbat")

CLEAR_SCREEN = "\033[H\033[2J"


class ExitCode(IntEnum):
    """Exit codes, also used by i3blocks to colour the block."""

    OK = 0
    NO_DATA = 1
    LOW_BATTERY = 2


def collect(
    client: BluezClient,
    cache: Cache,
    config: Config,
    *,
    refresh: bool = False,
) -> list[Keyboard]:
    """Read every matching keyboard, using the cache where it is allowed."""
    now = int(time.time())
    devices = client.devices(
        config.name_regex,
        any_battery=config.any_battery,
    )

    if config.device:
        needle = config.device.lower()
        devices = [
            device
            for device in devices
            if needle in device.address.lower() or needle in device.name.lower()
        ]

    keyboards: list[Keyboard] = []
    for device in devices:
        keyboard = Keyboard(
            address=device.address,
            name=device.name,
            path=device.path,
            connected=device.connected,
        )
        entry = cache.get(device.address)

        # A fresh cache entry saves a Bluetooth round trip on every bar tick.
        if entry and keyboard.connected and not refresh and entry.age(now) < config.ttl:
            keyboard.halves = list(entry.halves)
            keyboard.age = entry.age(now)
            keyboards.append(keyboard)
            continue

        if not keyboard.connected and config.connect and client.connect(device.path):
            time.sleep(1.0)
            keyboard.connected = True

        if keyboard.connected:
            try:
                keyboard.halves = client.read_halves(device.path)
            except BluezError as exc:
                keyboard.error = str(exc)
            if not keyboard.halves and not device.services_resolved:
                keyboard.error = "services not resolved yet (reconnecting)"

        if keyboard.halves and any(half.percent is not None for half in keyboard.halves):
            cache.put(keyboard, now)
        elif entry:
            keyboard.halves = list(entry.halves)
            keyboard.stale = True
            keyboard.age = entry.age(now)
        elif not keyboard.error:
            keyboard.error = "no data (device not connected?)"

        keyboards.append(keyboard)

    cache.save()
    return keyboards


def run_once(
    client: BluezClient,
    cache: Cache,
    config: Config,
    *,
    refresh: bool = False,
) -> tuple[str, ExitCode]:
    """Produce one output line and the matching exit code."""
    keyboards = collect(client, cache, config, refresh=refresh)
    output = format_output(config.format, keyboards, config)

    if not keyboards:
        return output, ExitCode.NO_DATA

    states = [
        (half_state(half, keyboard, zero_means_off=config.zero_means_off), half.percent)
        for keyboard in keyboards
        for half in keyboard.halves
    ]
    usable = [state for state, _ in states if state in (HalfState.OK, HalfState.STALE)]
    if not usable:
        return output, ExitCode.NO_DATA
    if any(
        state in (HalfState.OK, HalfState.STALE) and percent is not None and percent <= config.low
        for state, percent in states
    ):
        return output, ExitCode.LOW_BATTERY
    return output, ExitCode.OK


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (kept separate so tests can reuse it)."""
    parser = argparse.ArgumentParser(
        prog="zmkbat",
        description=(
            "Battery levels for both halves of a ZMK split keyboard, read from BlueZ over D-Bus."
        ),
        epilog=(
            "Exit codes: 0 ok, 1 no data, 2 charge at or below --low.\n"
            "Config file: ~/.config/zmkbat/config.json (optional)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-f",
        "--format",
        choices=OUTPUT_FORMATS,
        default=None,
        help="output format (default: text)",
    )
    parser.add_argument(
        "-d", "--device", default=None, help="address or name substring of the keyboard"
    )
    parser.add_argument(
        "-l", "--low", type=int, default=None, help="low battery threshold in percent (default: 20)"
    )
    parser.add_argument(
        "-t", "--ttl", type=int, default=None, help="cache lifetime in seconds (default: 30)"
    )
    parser.add_argument(
        "-w",
        "--watch",
        type=float,
        nargs="?",
        const=5.0,
        default=None,
        metavar="SEC",
        help="refresh continuously every SEC seconds (default: 5)",
    )
    parser.add_argument("--list", action="store_true", help="list Bluetooth devices and exit")
    parser.add_argument(
        "--connect", action="store_true", help="try to connect a disconnected keyboard"
    )
    parser.add_argument("--ascii", action="store_true", help="do not use Nerd Font icons")
    parser.add_argument("--name-regex", default=None, help="regular expression for device names")
    parser.add_argument(
        "--any-battery",
        action="store_true",
        help="select devices by Battery Service instead of by name",
    )
    parser.add_argument("--no-cache", action="store_true", help="neither read nor write the cache")
    parser.add_argument(
        "--refresh", action="store_true", help="ignore a fresh cache entry and read again"
    )
    parser.add_argument("--debug", action="store_true", help="enable debug logging and tracebacks")
    return parser


def _config_from_args(args: argparse.Namespace) -> Config:
    config = Config.load()
    return config.with_overrides(
        device=args.device,
        name_regex=args.name_regex,
        ttl=args.ttl,
        low=args.low,
        format=args.format,
        icons=False if args.ascii else None,
        connect=True if args.connect else None,
        any_battery=True if args.any_battery else None,
    )


def _print_list(client: BluezClient, config: Config) -> ExitCode:
    devices = client.devices(config.name_regex, all_devices=True)
    if not devices:
        print("zmkbat: no Bluetooth devices found", file=sys.stderr)
        return ExitCode.NO_DATA
    print(describe_devices(devices))
    return ExitCode.OK


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[], BluezClient] = DbusBluezClient,
) -> int:
    """Entry point; returns the process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="zmkbat: %(levelname)s: %(message)s",
    )

    try:
        config = _config_from_args(args)
    except ConfigError as exc:
        print(f"zmkbat: {exc}", file=sys.stderr)
        return ExitCode.NO_DATA

    try:
        client = client_factory()
    except BluezError as exc:
        print(f"zmkbat: {exc}", file=sys.stderr)
        return ExitCode.NO_DATA

    cache = Cache(enabled=not args.no_cache)

    try:
        if args.list:
            return _print_list(client, config)

        if args.watch is None:
            output, code = run_once(client, cache, config, refresh=args.refresh)
            print(output)
            return code

        interval = max(1.0, float(args.watch))
        while True:
            try:
                output, _ = run_once(client, cache, config, refresh=args.refresh)
            except BluezError as exc:
                output = f"zmkbat: {exc}"
            sys.stdout.write(CLEAR_SCREEN)
            sys.stdout.write(output + "\n")
            sys.stdout.write(f"\nupdated {time.strftime('%H:%M:%S')}  (Ctrl+C to quit)\n")
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        return ExitCode.OK
    except BluezError as exc:
        if args.debug:
            raise
        print(f"zmkbat: {exc}", file=sys.stderr)
        return ExitCode.NO_DATA
