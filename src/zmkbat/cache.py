"""On-disk cache of the last known battery readings.

Status bars poll their scripts far more often than a battery level can change,
and every GATT read is a Bluetooth round trip. The cache serves two purposes:

* rate-limit reads to one per ``ttl`` seconds;
* keep showing the last known values while the keyboard is asleep or
  disconnected, clearly marked as stale by the formatters.

The file is written atomically (temporary file + ``os.replace``) so that a
crash or a concurrent invocation can never leave a half-written JSON behind.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import Half, Keyboard, Role

SCHEMA_VERSION = 1


def default_cache_path() -> Path:
    """``$XDG_CACHE_HOME/zmkbat/state.json`` (``~/.cache`` by default)."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "zmkbat" / "state.json"


@dataclass(slots=True)
class CacheEntry:
    """Last known readings for one device."""

    name: str
    updated: int
    halves: list[Half]

    def age(self, now: int | None = None) -> int:
        """Seconds since the entry was written (never negative)."""
        current = int(time.time()) if now is None else now
        return max(0, current - self.updated)


class Cache:
    """A tiny JSON-backed cache; disabled instances are no-ops."""

    def __init__(self, path: Path | None = None, *, enabled: bool = True) -> None:
        self.path = path or default_cache_path()
        self.enabled = enabled
        self._entries: dict[str, CacheEntry] = {}
        self._dirty = False
        if enabled:
            self._load()

    # -- public API --------------------------------------------------------

    def get(self, address: str) -> CacheEntry | None:
        """Return the cached entry for ``address``, if any."""
        return self._entries.get(address)

    def put(self, keyboard: Keyboard, now: int | None = None) -> None:
        """Store the readings of ``keyboard``."""
        if not self.enabled:
            return
        self._entries[keyboard.address] = CacheEntry(
            name=keyboard.name,
            updated=int(time.time()) if now is None else now,
            halves=[
                Half(role=half.role, percent=half.percent, label=half.label)
                for half in keyboard.halves
            ],
        )
        self._dirty = True

    def save(self) -> None:
        """Flush to disk if anything changed. Failures are not fatal."""
        if not self.enabled or not self._dirty:
            return
        payload = {
            "version": SCHEMA_VERSION,
            "devices": {
                address: {
                    "name": entry.name,
                    "updated": entry.updated,
                    "halves": [
                        {"role": half.role.value, "percent": half.percent, "label": half.label}
                        for half in entry.halves
                    ],
                }
                for address, entry in self._entries.items()
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            # A read-only or full cache directory must not break the tool.
            return
        self._dirty = False

    # -- internals ---------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return
        if not isinstance(data, dict) or data.get("version") != SCHEMA_VERSION:
            return
        devices = data.get("devices")
        if not isinstance(devices, dict):
            return
        for address, entry in devices.items():
            parsed = _parse_entry(entry)
            if parsed is not None:
                self._entries[str(address)] = parsed


def _parse_entry(raw: Any) -> CacheEntry | None:
    if not isinstance(raw, dict):
        return None
    halves: list[Half] = []
    for item in raw.get("halves", []):
        if not isinstance(item, dict):
            continue
        try:
            role = Role(str(item.get("role", Role.CENTRAL.value)))
        except ValueError:
            continue
        percent = item.get("percent")
        halves.append(
            Half(
                role=role,
                percent=percent if isinstance(percent, int) else None,
                label=str(item.get("label", "")),
            )
        )
    updated = raw.get("updated")
    if not isinstance(updated, int):
        return None
    return CacheEntry(name=str(raw.get("name", "")), updated=updated, halves=halves)
