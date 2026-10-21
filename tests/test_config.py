"""Tests for configuration loading and validation."""

from __future__ import annotations

import json

import pytest

from zmkbat.config import Config, ConfigError, default_config_path
from zmkbat.model import Role


def test_defaults():
    config = Config()
    assert config.ttl == 30
    assert config.low == 20
    assert config.format == "text"
    assert config.icons is True
    assert config.zero_means_off is True
    assert config.label_for(Role.CENTRAL) == "L"
    assert config.label_for(Role.PERIPHERAL) == "R"


def test_missing_file_yields_defaults(tmp_path):
    assert Config.load(tmp_path / "nope.json") == Config()


def test_load_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "ttl": 5,
                "low": 10,
                "format": "polybar",
                "labels": {"central": "A", "peripheral": "B"},
            }
        ),
        encoding="utf-8",
    )
    config = Config.load(path)
    assert config.ttl == 5
    assert config.low == 10
    assert config.format == "polybar"
    assert config.label_for(Role.CENTRAL) == "A"


def test_unknown_keys_are_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tttl": 5}), encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown config keys: tttl"):
        Config.load(path)


def test_invalid_json_is_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid JSON"):
        Config.load(path)


def test_non_object_json_is_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON object"):
        Config.load(path)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"ttl": -1}, "ttl"),
        ({"low": 101}, "low"),
        ({"low": -1}, "low"),
        ({"format": "yaml"}, "unknown format"),
        ({"name_regex": "("}, "invalid name_regex"),
        ({"labels": {"central": "L"}}, "labels"),
    ],
)
def test_validation(kwargs, message):
    with pytest.raises(ConfigError, match=message):
        Config(**kwargs)


def test_overrides_ignore_none():
    config = Config(ttl=10)
    assert config.with_overrides(ttl=None, low=None) is config
    assert config.with_overrides(ttl=99).ttl == 99


def test_overrides_are_validated():
    with pytest.raises(ConfigError):
        Config().with_overrides(low=1000)


def test_default_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_path() == tmp_path / "zmkbat" / "config.json"
