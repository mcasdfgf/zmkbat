# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-21

### Added

- Read both halves of a ZMK split keyboard over BlueZ D-Bus, distinguishing the
  proxied peripheral characteristic by its `0x2901` user description.
- Output formats: `text`, `plain`, `polybar`, `waybar`, `json`.
- JSON cache with a configurable TTL, atomic writes and schema versioning.
- Explicit states: `ok`, `stale`, `off`, `unknown`; a zero from the peripheral
  half is reported as `off` rather than `0 %`.
- Exit codes `0` / `1` / `2` for scripts and i3blocks.
- `--list`, `--watch`, `--connect`, `--refresh`, `--no-cache`, `--ascii`,
  `--name-regex`, `--any-battery`, `--debug`.
- Optional config file at `~/.config/zmkbat/config.json`.
- Status bar snippets for polybar, waybar and i3blocks.
- Test suite that runs without a Bluetooth adapter.

[Unreleased]: https://github.com/mcasdfgf/zmkbat/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mcasdfgf/zmkbat/releases/tag/v0.1.0
