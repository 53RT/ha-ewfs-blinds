# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`end_stop_buffer` config option** (default `0.0` s, i.e. disabled) for single shutters
  and native remote groups.
  When set to a positive value, the stop timer is extended by this many seconds **only when
  moving to the physical end-stops** (fully open `100 %` or fully closed `0 %`).  The motor
  cuts off automatically at its mechanical end-stop, so the overrun is completely harmless.
  This compensates for a slightly under-estimated `travel_time_*` and resets accumulated
  position drift on every full open/close cycle.
  - The extension applies only to the hardware stop timer, not to the position-tracking
    duration, so the position estimate remains accurate for intermediate manual stops during
    normal travel.
  - Works for both hardware-commanded and simulated moves (`simulate_command`).
  - The `end_stop_buffer` value is exposed as a state attribute for easy inspection.

- **`tilt_step_count` config option** (default `7`, range `2`–`20`) for single shutters and
  native remote groups.
  Previously the number of discrete tilt positions was hardcoded to `7` (the value used by
  Warema EWFS shutters, giving ~16 ° per step).  This option makes the integration usable
  with other manufacturers or models that have a different slat step count.
  - All tilt operations (`open_cover_tilt`, `close_cover_tilt`, `set_cover_tilt_position`,
    `simulate_command`, `simulate_set_tilt_position`, `set_cover_position_and_tilt_step`)
    respect the configured step count.
  - `warema_ewfs.set_cover_position_and_tilt_step` accepts step indices from `0` to
    `tilt_step_count − 1`; values beyond the maximum are clamped.
  - The `tilt_steps` state attribute now reflects the entity's configured step count rather
    than the hardcoded constant.

### Changed

- **`warema_ewfs.set_cover_position_and_tilt_step` service schema**: the maximum accepted
  `tilt_step` value in `services.yaml` was raised from `6` to `19` to accommodate entities
  configured with up to 20 tilt steps.  Per-entity clamping ensures correctness regardless
  of the configured `tilt_step_count`.

### Removed

- **Dead tilt-animation scaffolding** that was never activated: the instance variables
  `_tilt_direction`, `_tilt_started_at`, `_tilt_duration`, `_tilt_start_pos`,
  `_tilt_target_pos`, and `_unsub_tilt_timer`; the methods `_schedule_tilt_stop` and
  `_finish_tilt_move`; and the corresponding dead branch in `_refresh_estimates`.
  This had no effect on runtime behaviour.
- **Commented-out alternative implementations** of `async_open_cover_tilt` /
  `async_close_cover_tilt` that were superseded in a previous refactor.

### Refactored

- Extracted `_end_stop_timer_duration(duration, target)` helper on `WaremaEWFSCover`
  to de-duplicate the end-stop buffer calculation that appeared in both `_start_cover_move`
  and `_simulate_cover_move`.
- `WaremaEWFSGroupCover._revalidate_group_members` now calls `_is_valid_warema_single_member`
  directly instead of going through the thin `_is_valid_member` instance-method wrapper
  (which has been removed).
- `_cleanup_interval_listener` no longer checks the now-removed `_tilt_direction` field.

## [0.1.3] - 2026-06-04

### Fixed

- **Simulated move did not update tilt when cover was already at the target position.**
  When `simulate_command("close")` was called on a cover already at position `0`, or
  `simulate_command("open")` was called on a cover already at `100`, the early return
  in `_simulate_cover_move` skipped the tilt update entirely.  The slats now correctly
  reflect vertical (`0%`) after a close and horizontal (`100%`) after an open, even
  when no physical movement is needed.

### Added

- **`simulate_stop_delay` config option** (default `0.0` s, i.e. disabled).
  When set to a positive value, the integration automatically sends a real hardware
  `stop` command this many seconds **after the cover has finished its tracked movement**
  (i.e. after `_finish_cover_move` runs), not at the time the command is received.
  This solves a hardware limitation of WAREMA motors: after moving in one direction
  without a stop, the motor is direction-locked and needs either a stop or a
  double-press of the opposite direction before it can reverse.  When a human uses the
  physical remote (and the ESPHome automation calls `simulate_command`), no stop is
  sent automatically; this option bridges that gap.
  - The timer starts only for *simulated* moves (`simulate_command`) — normal
    hardware-commanded moves are unaffected.
  - The delay runs from the moment the integration's tracking says the cover has
    reached its target, giving the motor time to physically come to rest before the
    neutralising stop is sent.
  - The timer is cancelled automatically if the cover stops for any other reason
    (explicit stop command, new move started).
  - The `simulate_stop_delay` value is exposed as a state attribute for easy inspection.


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
