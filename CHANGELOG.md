# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-28

### Added

- Initial release of the Warema EWFS Cover integration.
- **Single shutter** support: map five logical commands (`open`, `close`, `stop`, `tilt_up`, `tilt_down`) to ESPHome `button` entities.
- Time-based (optimistic) position and tilt tracking with configurable travel times per shutter.
- 7 fixed tilt steps with configurable time per step (up / down).
- Position and tilt state is persisted and restored across Home Assistant restarts.
- **Fan-out group** cover: fans out cover commands to multiple single-shutter members with an optional delay between commands.
- **Native remote group** cover: uses a dedicated set of group command buttons; syncs member shutter state automatically.
- Full UI Config Flow and Options Flow (no YAML required).
- YAML platform configuration (`configuration.yaml`) still supported.
- Custom services:
  - `warema_ewfs.send_command` — send a named command to a shutter.
  - `warema_ewfs.set_cover_position_and_tilt` — move to position then set tilt in one action.
  - `warema_ewfs.set_cover_position_and_tilt_step` — move to position then set tilt by discrete step (0–6).
  - `warema_ewfs.simulate_command` — update tracked state as if an external remote sent a command.
  - `warema_ewfs.simulate_set_tilt_position` — set tilt position without sending a hardware command.
  - `warema_ewfs.force_move` — force open/close regardless of current tracked state.
- German (`de`) and English (`en`) UI translations.
- HACS compatibility.
