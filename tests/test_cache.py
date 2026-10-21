"""Tests for the JSON cache."""

from __future__ import annotations

import json

from zmkbat.cache import SCHEMA_VERSION, Cache
from zmkbat.model import Half, Role


def test_roundtrip_through_disk(tmp_path, keyboard_factory, both_halves):
    path = tmp_path / "state.json"
    cache = Cache(path)
    cache.put(keyboard_factory(both_halves), now=1000)
    cache.save()

    reloaded = Cache(path)
    entry = reloaded.get("F9:8F:6F:47:37:0A")
    assert entry is not None
    assert entry.name == "EH K:03 v4"
    assert entry.updated == 1000
    assert [(half.role, half.percent) for half in entry.halves] == [
        (Role.CENTRAL, 100),
        (Role.PERIPHERAL, 100),
    ]


def test_age_is_never_negative(tmp_path, keyboard_factory, both_halves):
    cache = Cache(tmp_path / "state.json")
    cache.put(keyboard_factory(both_halves), now=2000)
    entry = cache.get("F9:8F:6F:47:37:0A")
    assert entry.age(now=2000) == 0
    assert entry.age(now=1500) == 0
    assert entry.age(now=2420) == 420


def test_disabled_cache_is_a_noop(tmp_path, keyboard_factory, both_halves):
    path = tmp_path / "state.json"
    cache = Cache(path, enabled=False)
    cache.put(keyboard_factory(both_halves))
    cache.save()
    assert cache.get("F9:8F:6F:47:37:0A") is None
    assert not path.exists()


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    assert Cache(path).get("anything") is None


def test_unknown_schema_version_is_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": SCHEMA_VERSION + 1, "devices": {}}), encoding="utf-8")
    assert Cache(path).get("anything") is None


def test_malformed_entries_are_skipped(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "version": SCHEMA_VERSION,
                "devices": {
                    "AA:BB": {"name": "x", "updated": "yesterday", "halves": []},
                    "CC:DD": {
                        "name": "ok",
                        "updated": 10,
                        "halves": [
                            {"role": "central", "percent": 50, "label": ""},
                            {"role": "nonsense", "percent": 1},
                            {"role": "peripheral", "percent": "high"},
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    cache = Cache(path)
    assert cache.get("AA:BB") is None
    entry = cache.get("CC:DD")
    assert entry is not None
    assert [(half.role, half.percent) for half in entry.halves] == [
        (Role.CENTRAL, 50),
        (Role.PERIPHERAL, None),
    ]


def test_save_is_atomic_and_leaves_no_temporary_file(tmp_path, keyboard_factory, both_halves):
    path = tmp_path / "state.json"
    cache = Cache(path)
    cache.put(keyboard_factory(both_halves))
    cache.save()
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()


def test_save_without_changes_does_not_touch_the_file(tmp_path, keyboard_factory, both_halves):
    path = tmp_path / "state.json"
    cache = Cache(path)
    cache.put(keyboard_factory(both_halves))
    cache.save()
    first = path.stat().st_mtime_ns
    cache.save()
    assert path.stat().st_mtime_ns == first


def test_unwritable_directory_does_not_raise(tmp_path, keyboard_factory, both_halves):
    path = tmp_path / "missing" / "state.json"
    path.parent.mkdir()
    path.parent.chmod(0o500)
    try:
        cache = Cache(path)
        cache.put(keyboard_factory(both_halves))
        cache.save()  # must not raise
    finally:
        path.parent.chmod(0o700)


def test_put_copies_halves(tmp_path, keyboard_factory):
    halves = [Half(Role.CENTRAL, 42)]
    cache = Cache(tmp_path / "state.json")
    cache.put(keyboard_factory(halves))
    halves[0].percent = 1
    assert cache.get("F9:8F:6F:47:37:0A").halves[0].percent == 42
