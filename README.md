# Warema EWFS Home Assistant Custom Component

This project provides a custom `cover` platform for Warema EWFS shutters.
It is designed for setups where an ESPHome device already exposes one `button` entity
per shutter command.

Supported commands per shutter:
- `open` (fully open)
- `close` (fully close)
- `stop`
- `tilt_up`
- `tilt_down`

The integration is time-based (optimistic):
- individual travel times per shutter (`up` / `down`)
- 7 fixed tilt steps
- configurable time per tilt step (`up` / `down`)
- `position` and `tilt_position` are tracked and restored by Home Assistant

## Project Structure

- `custom_components/warema_ewfs/cover.py`: Home Assistant cover entities (single + group)
- `custom_components/warema_ewfs/model.py`: pure timing/position helpers (testable without HA)
- `custom_components/warema_ewfs/services.yaml`: entity service `send_command`

## Installation in Home Assistant

1. Copy `custom_components/warema_ewfs` into your Home Assistant config directory.
2. Restart Home Assistant.
3. Configure shutters and optional groups in `configuration.yaml`.

## Configuration Model

### Single Shutter

For each shutter, you map logical commands to existing ESPHome `button` entities.
No `command_repeat` is needed.

Required keys:
- `btn_open`
- `btn_close`
- `btn_stop`
- `btn_tilt_up`
- `btn_tilt_down`

Optional keys:
- `travel_time_up` (seconds from 0% to 100%)
- `travel_time_down` (seconds from 100% to 0%)
- `tilt_step_time_up` (seconds per tilt step toward 100%)
- `tilt_step_time_down` (seconds per tilt step toward 0%)
- `send_stop_after_move` (default `true`, sends `btn_stop` when a normal up/down move reaches target)
- `unique_id`
- `shutter_id`

Behavior note:
- `send_stop_after_move` is applied only to normal cover movement (`open` / `close` / `set_position`).
- Tilt movement completion never sends an automatic stop command.
- Tilt is applied by repeating `tilt_up`/`tilt_down` commands per step (about 16 degrees per command).

Combined move behavior:
- The service `cover.set_cover_position_and_tilt` first moves to the target cover position.
- After the move, tilt base orientation is inferred from move direction:
  - upward move → slats horizontal (`100%` tilt)
  - downward move → slats vertical (`0%` tilt)
- Then tilt is adjusted to the requested target.
- You can also use `cover.set_cover_position_and_tilt_step` with discrete tilt steps (`0..6`).

### Group Shutter

A group is defined as another `cover` entry with:
- `is_group: true`
- `group_members`: list of member `cover` entity IDs

When a group is controlled, commands are fanned out to all members via Home Assistant
cover services. This ensures member shutters update their own position/tilt tracking.

Group members are validated at runtime:
- only `warema_ewfs` single-cover entities are accepted as valid members
- non-Warema entities (or nested groups) are ignored and logged as warnings

### Native Remote Group Shutter

For native Warema remote groups (one shared set of group commands), use:
- `is_native_group: true`
- `group_members`: list of member `cover` entity IDs
- the five group command buttons: `btn_open`, `btn_close`, `btn_stop`, `btn_tilt_up`, `btn_tilt_down`

Behavior:
- Cover movement supports only fully open (`100%`) and fully closed (`0%`).
- Intermediate cover targets are not supported and will be snapped to full open/close.
- Group travel time is derived from the longest member travel time (`travel_time_up` / `travel_time_down`).
- Tilt is fully supported via repeated tilt commands.

## YAML Example

```yaml
cover:
  - platform: warema_ewfs
	name: Kitchen
	unique_id: warema_kitchen
	shutter_id: kitchen

	btn_open: button.kitchen_shutter_open
	btn_close: button.kitchen_shutter_close
	btn_stop: button.kitchen_shutter_stop
	btn_tilt_up: button.kitchen_shutter_tilt_up
	btn_tilt_down: button.kitchen_shutter_tilt_down

	travel_time_up: 29.5
	travel_time_down: 31.0
	tilt_step_time_up: 0.35
	tilt_step_time_down: 0.45
	send_stop_after_move: true

  - platform: warema_ewfs
	name: Living Room
	unique_id: warema_living_room
	shutter_id: living_room

	btn_open: button.living_room_shutter_open
	btn_close: button.living_room_shutter_close
	btn_stop: button.living_room_shutter_stop
	btn_tilt_up: button.living_room_shutter_tilt_up
	btn_tilt_down: button.living_room_shutter_tilt_down

	travel_time_up: 24
	travel_time_down: 26
	tilt_step_time_up: 0.30
	tilt_step_time_down: 0.35
	send_stop_after_move: true

  - platform: warema_ewfs
	name: Downstairs Group
	unique_id: warema_downstairs_group
	is_group: true
	group_members:
	  - cover.kitchen
	  - cover.living_room

  - platform: warema_ewfs
	name: Ground Floor Native Group
	unique_id: warema_ground_floor_native
	is_native_group: true
	group_members:
	  - cover.kitchen
	  - cover.living_room

	btn_open: button.ground_floor_open
	btn_close: button.ground_floor_close
	btn_stop: button.ground_floor_stop
	btn_tilt_up: button.ground_floor_tilt_up
	btn_tilt_down: button.ground_floor_tilt_down
```

## Config Flow (UI)

The current implementation is YAML-based.
If/when a Config Flow is added, it should expose the same fields:

- single shutter: five `btn_*` entities + timing values
- fan-out group shutter: `is_group` and `group_members`
- native remote group shutter: `is_native_group`, `group_members`, and five group `btn_*` entities

## Service Example (Position + Tilt)

```yaml
service: cover.set_cover_position_and_tilt
target:
  entity_id: cover.kitchen
data:
  position: 50
  tilt_position: 67
```

## Service Example (Position + Tilt Step)

`tilt_step` mapping for 7 steps:
- `0, 1, 2, 3, 4, 5, 6` -> `0%, 17%, 33%, 50%, 67%, 83%, 100%`
- Example: target around 45 degrees is typically `tilt_step: 3` (about 50%).

```yaml
service: cover.set_cover_position_and_tilt_step
target:
  entity_id: cover.kitchen
data:
  position: 50
  tilt_step: 4
```

## Local Quick Test

```zsh
python -m pip install -e '.[dev]'
pytest
python main.py
```

## Calibration and Notes

- Measure `travel_time_up` and `travel_time_down` separately for each shutter.
- Fine-tune tilt using the 7-step model and per-step timing values.
- Without physical feedback, position is estimated from elapsed time.
- Manual wall-remote usage can temporarily introduce drift until HA sends a new command.

