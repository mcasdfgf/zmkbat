"""Tests for the CLI: collection, exit codes and argument handling."""

from __future__ import annotations

import json

import pytest

from zmkbat.cache import Cache
from zmkbat.cli import ExitCode, collect, main, run_once
from zmkbat.config import Config
from zmkbat.model import Half, Role

from .conftest import FakeClient


@pytest.fixture
def config() -> Config:
    return Config()


def test_run_once_ok(fake_client_factory, device_info, both_halves, config):
    client = FakeClient([device_info], {device_info.path: both_halves})
    output, code = run_once(client, Cache(), config)
    assert code is ExitCode.OK
    assert "100%" in output


def test_run_once_low_battery(fake_client_factory, device_info, config):
    halves = [Half(Role.CENTRAL, 15), Half(Role.PERIPHERAL, 8, "Peripheral 0")]
    client = FakeClient([device_info], {device_info.path: halves})
    _, code = run_once(client, Cache(), config)
    assert code is ExitCode.LOW_BATTERY


def test_run_once_ignores_off_peripheral_for_the_exit_code(device_info, config):
    halves = [Half(Role.CENTRAL, 100), Half(Role.PERIPHERAL, 0, "Peripheral 0")]
    client = FakeClient([device_info], {device_info.path: halves})
    _, code = run_once(client, Cache(), config)
    assert code is ExitCode.OK


def test_run_once_no_devices(config):
    _, code = run_once(FakeClient(), Cache(), config)
    assert code is ExitCode.NO_DATA


def test_run_once_no_readings(device_info, config):
    halves = [Half(Role.CENTRAL, None), Half(Role.PERIPHERAL, None)]
    client = FakeClient([device_info], {device_info.path: halves})
    _, code = run_once(client, Cache(), config)
    assert code is ExitCode.NO_DATA


def test_collect_uses_the_cache_within_ttl(device_info, both_halves, config):
    client = FakeClient([device_info], {device_info.path: both_halves})
    cache = Cache()
    collect(client, cache, config)
    collect(client, cache, config)
    assert client.reads == 1


def test_collect_refresh_bypasses_the_cache(device_info, both_halves, config):
    client = FakeClient([device_info], {device_info.path: both_halves})
    cache = Cache()
    collect(client, cache, config)
    collect(client, cache, config, refresh=True)
    assert client.reads == 2


def test_collect_falls_back_to_the_cache_when_disconnected(device_info, both_halves, config):
    client = FakeClient([device_info], {device_info.path: both_halves})
    cache = Cache()
    collect(client, cache, config)

    offline = type(device_info)(
        path=device_info.path,
        address=device_info.address,
        name=device_info.name,
        connected=False,
        paired=True,
        services_resolved=False,
        has_battery_service=True,
        matches_name=True,
    )
    keyboards = collect(FakeClient([offline]), cache, config)
    assert keyboards[0].stale is True
    assert keyboards[0].halves[0].percent == 100


def test_collect_reports_missing_data(device_info, config):
    offline = type(device_info)(
        path=device_info.path,
        address=device_info.address,
        name=device_info.name,
        connected=False,
        paired=True,
        services_resolved=False,
        has_battery_service=True,
        matches_name=True,
    )
    keyboards = collect(FakeClient([offline]), Cache(), config)
    assert keyboards[0].error == "no data (device not connected?)"


def test_collect_connects_when_asked(device_info, both_halves):
    offline = type(device_info)(
        path=device_info.path,
        address=device_info.address,
        name=device_info.name,
        connected=False,
        paired=True,
        services_resolved=True,
        has_battery_service=True,
        matches_name=True,
    )
    client = FakeClient([offline], {device_info.path: both_halves})
    keyboards = collect(client, Cache(), Config(connect=True))
    assert client.connects == 1
    assert keyboards[0].connected is True


def test_collect_filters_by_device(device_info, both_halves, config):
    client = FakeClient([device_info], {device_info.path: both_halves})
    assert collect(client, Cache(), config.with_overrides(device="zzz")) == []
    assert len(collect(client, Cache(), config.with_overrides(device="k:03"))) == 1


def test_main_prints_and_returns_the_exit_code(device_info, both_halves, capsys):
    client = FakeClient([device_info], {device_info.path: both_halves})
    code = main(["-f", "plain"], client_factory=lambda: client)
    assert code == ExitCode.OK
    assert capsys.readouterr().out.strip() == "100 100"


def test_main_list(device_info, capsys):
    client = FakeClient([device_info])
    code = main(["--list"], client_factory=lambda: client)
    assert code == ExitCode.OK
    assert "F9:8F:6F:47:37:0A" in capsys.readouterr().out


def test_main_list_without_devices(capsys):
    code = main(["--list"], client_factory=FakeClient)
    assert code == ExitCode.NO_DATA
    assert "no Bluetooth devices" in capsys.readouterr().err


def test_main_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"], client_factory=FakeClient)
    assert excinfo.value.code == 0
    assert "zmkbat" in capsys.readouterr().out


def test_main_rejects_invalid_config(tmp_path, capsys):
    config_dir = tmp_path / "config" / "zmkbat"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(json.dumps({"low": 500}), encoding="utf-8")
    code = main([], client_factory=FakeClient)
    assert code == ExitCode.NO_DATA
    assert "low must be between" in capsys.readouterr().err


def test_main_json_output(device_info, both_halves, capsys):
    client = FakeClient([device_info], {device_info.path: both_halves})
    main(["-f", "json"], client_factory=lambda: client)
    payload = json.loads(capsys.readouterr().out)
    assert payload["keyboards"][0]["halves"][1]["label"] == "Peripheral 0"
