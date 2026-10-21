"""Configuration loading, validation and CLI overrides.

The configuration is a small JSON file (``~/.config/zmkbat/config.json``) so
that it can be edited by hand and parsed without extra dependencies. Every
value can be overridden from the command line; ``None`` means "not given".
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from .model import Role

#: Device names that are likely to be a ZMK split keyboard. Users with an
#: unusual name can pass ``--name-regex`` or ``--any-battery``.
DEFAULT_NAME_REGEX = (
    r"(?i)(zmk|ergohaven|\bEH\b|k:0|corne|sofle|lily58|kyria|ferris|totem"
    r"|chocofi|piantor|voyager|glove80)"
)

OUTPUT_FORMATS: tuple[str, ...] = ("text", "plain", "polybar", "waybar", "json")


class ConfigError(ValueError):
    """Raised when the configuration file or a CLI value is invalid."""


def default_config_path() -> Path:
    """``$XDG_CONFIG_HOME/zmkbat/config.json`` (``~/.config`` by default)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "zmkbat" / "config.json"


@dataclass(slots=True)
class Config:
    """Effective configuration: file values merged with CLI overrides."""

    device: str | None = None
    """Address or name substring of the keyboard to use; ``None`` = all."""

    name_regex: str = DEFAULT_NAME_REGEX
    ttl: int = 30
    """How long a cached reading is considered fresh, in seconds."""

    low: int = 20
    """Threshold for the "low battery" exit code and colour, in percent."""

    format: str = "text"
    icons: bool = True
    labels: dict[str, str] = field(default_factory=lambda: {"central": "L", "peripheral": "R"})
    connect: bool = False
    """Try to connect a disconnected keyboard instead of only using the cache."""

    zero_means_off: bool = True
    """Treat a zero reading from the peripheral half as "off", not "empty"."""

    any_battery: bool = False
    """Select devices by Battery Service instead of by name."""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise :class:`ConfigError` if any value is out of range."""
        if self.ttl < 0:
            raise ConfigError(f"ttl must be >= 0, got {self.ttl}")
        if not 0 <= self.low <= 100:
            raise ConfigError(f"low must be between 0 and 100, got {self.low}")
        if self.format not in OUTPUT_FORMATS:
            raise ConfigError(
                f"unknown format {self.format!r}, expected one of {', '.join(OUTPUT_FORMATS)}"
            )
        try:
            re.compile(self.name_regex)
        except re.error as exc:
            raise ConfigError(f"invalid name_regex: {exc}") from exc
        for role in Role:
            if role.value not in self.labels:
                raise ConfigError(f"labels must define {role.value!r}")

    def label_for(self, role: Role) -> str:
        """Short label used in status bars (``L``/``R`` by default)."""
        return str(self.labels.get(role.value, role.value[0].upper()))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Config:
        """Build a config from a JSON-like mapping, rejecting unknown keys."""
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ConfigError(f"unknown config keys: {', '.join(unknown)}")
        return cls(**dict(data))

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load the config file; a missing file yields the defaults."""
        path = path or default_config_path()
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls()
        except OSError as exc:
            raise ConfigError(f"cannot read {path}: {exc}") from exc
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"{path} must contain a JSON object")
        return cls.from_mapping(data)

    def with_overrides(self, **overrides: Any) -> Config:
        """Return a copy with the non-``None`` overrides applied."""
        clean = {key: value for key, value in overrides.items() if value is not None}
        return replace(self, **clean) if clean else self
