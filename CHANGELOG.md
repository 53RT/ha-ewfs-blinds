# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-05-29

### Fixed

- **State restore after HA restart**: position and tilt were never restored because the restore logic
  was reading the service-call attribute key `position` instead of the state attribute key
  `current_position` (`ATTR_CURRENT_POSITION` / `ATTR_CURRENT_TILT_POSITION`).

### Changed

- **Group covers no longer track position/tilt state.** Both `WaremaEWFSGroupCover` (fan-out) and
  `WaremaEWFSNativeGroupCover` (native remote) now always return `None` for
  `current_cover_position`, `current_cover_tilt_position`, and `is_closed`.
  Individual member shutters can be moved independently, making group-level state impossible
  to keep in sync reliably.
  - `WaremaEWFSGroupCover` no longer inherits from `RestoreEntity` and does not restore or persist
    any position/tilt state.
  - `WaremaEWFSNativeGroupCover` retains internal position tracking for movement-timing
    calculations only; the values are no longer exposed to Home Assistant.
  - `async_open_cover_tilt` / `async_close_cover_tilt` on the fan-out group now forward
    `open_cover_tilt` / `close_cover_tilt` directly to member entities instead of computing
    a target step from the (now absent) group state.

### Added

- Default entity icon `mdi:blinds` set via `_attr_icon` on all three cover entity classes.
- Regression tests for state restore covering both the correct `current_position` attribute
  key and a negative test that the old wrong `position` key is not picked up.

### Removed

- `entity` section from `icons.json` — it conflicted with hassfest validation and is superseded
  by `_attr_icon` on the entity classes.
- Redundant explicit `voluptuous` dev dependency (already provided transitively by `homeassistant`).
- Unused `matplotlib` production dependency.

## [0.1.1] - 2026-05-28

### Fixed

- Corrected the hassfest CI action reference from the deprecated `home-assistant/action-hassfest@master`
  to `home-assistant/actions/hassfest@master`.
- Removed invalid `entity` block from `icons.json` that caused hassfest validation failures.

### Added

- Brand icon (`custom_components/warema_ewfs/brand/icon.png`) for HACS and the HA brand registry.

### Changed

- Cleaned up field ordering in `manifest.json` (no functional change).
- Removed duplicate CI workflow file.

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
