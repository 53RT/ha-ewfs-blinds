# Warema EWFS Cover — Home Assistant Integration

> **Full Home Assistant control for Warema EWFS shutters** — including precise position
> tracking, slat tilt, group management, and seamless co-existence with physical remotes.
> No proprietary hub or cloud required.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![HA min version](https://img.shields.io/badge/Home%20Assistant-%3E%3D%202024.1-blue.svg)](https://www.home-assistant.io/)

---

## Supported Features

Warema EWFS shutters communicate over a proprietary RF protocol and do not expose any
position feedback to the controller.  Out of the box, Home Assistant has no way to
know where a shutter is, let alone control slat tilt at a specific angle.

This integration solves that by bridging the gap between an ESPHome RF transmitter
(or any other remote that exposes HA `button` entities) and the native Home Assistant
`cover` platform:

| Feature                          | Details |
|----------------------------------|---|
| **Full position control**        | Open, close, or move to any percentage — tracked by elapsed time |
| **Slat tilt control**            | Configurable discrete tilt steps (default 7, ~16 ° each), individually tunable per direction |
| **Persistent state**             | Position and tilt survive Home Assistant restarts |
| **UI-first setup**               | Complete Config Flow and Options Flow — no YAML needed |
| ️ **Group support**              | Fan-out groups and native Warema remote groups |
| **Physical remote co-existence** | `simulate_command` keeps HA in sync when a wall remote is used |
| **Hardware quirk handling**      | `simulate_stop_delay` neutralises the WAREMA motor direction lock |
| **End-stop drift correction**    | `end_stop_buffer` adds a safe overrun margin on full open/close to correct accumulated timing drift |
| **Multi-manufacturer support**   | `tilt_step_count` makes the integration usable with non-Warema covers that have a different slat step count |
| ️ **Custom services**            | Force-move, combined position+tilt, discrete tilt steps, and more |

---

## Requirements

- Home Assistant ≥ 2024.1
- An ESPHome device (or equivalent) that exposes one `button` entity per shutter command,
  **or** any other mechanism that lets Home Assistant press a button to fire an RF command.
  See the companion repository [esphome-ewfs](https://github.com/53RT/esphome-ewfs) for a
  ready-made ESPHome configuration.

---

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** → three-dot menu → **Custom repositories**.
3. Add `https://github.com/53RT/ha-ewfs-blinds` and select **Integration** as the category.
4. Search for *Warema EWFS Cover* and install it.
5. Restart Home Assistant.
6. Go to **Settings** → **Devices & Services** → **Add Integration** and search for
   *Warema EWFS Cover* to set up your first shutter.

### Manual

1. Copy the `custom_components/warema_ewfs/` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings** → **Devices & Services** → **Add Integration** and search for
   *Warema EWFS Cover*.

---

## Supported Commands

Each shutter maps five logical commands to existing Home Assistant `button` entities:

| Command | Effect |
|---|---|
| `open` | Move shutter fully open |
| `close` | Move shutter fully closed |
| `stop` | Halt movement immediately |
| `tilt_up` | Rotate slats one step toward horizontal (100 %) |
| `tilt_down` | Rotate slats one step toward vertical (0 %) |

The number of slat steps is configurable via `tilt_step_count` (default `7`).
One step always moves from the current position to the next discrete step.

---

## Configuration

### Option A — UI Config Flow (recommended)

No YAML required.  After installing the integration:

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for *Warema EWFS Cover*.
3. Choose a cover type and follow the wizard:
   - **Single shutter** — map the five `btn_*` button entities and set travel/tilt times.
   - **Fan-out group** — pick member cover entities and optionally set a command delay.
   - **Native remote group** — map five group `btn_*` button entities, pick member covers.
4. All settings can be changed later via the integration's **Configure** button (Options Flow).

### Option B — YAML (`configuration.yaml`)

<details>
<summary>Show full YAML example</summary>

```yaml
cover:
  # ── Single shutter ────────────────────────────────────────────────────────
  - platform: warema_ewfs
    name: Kitchen
    unique_id: warema_kitchen

    btn_open:      button.kitchen_shutter_open
    btn_close:     button.kitchen_shutter_close
    btn_stop:      button.kitchen_shutter_stop
    btn_tilt_up:   button.kitchen_shutter_tilt_up
    btn_tilt_down: button.kitchen_shutter_tilt_down

    travel_time_up:      29.5   # seconds, fully closed → fully open
    travel_time_down:    31.0   # seconds, fully open   → fully closed
    tilt_step_time_up:    0.35  # seconds per tilt step toward 100 %
    tilt_step_time_down:  0.45  # seconds per tilt step toward 0 %
    send_stop_after_move: true
    simulate_stop_delay:  3.0   # send stop 3 s after a simulated move finishes
    end_stop_buffer:      2.0   # extend stop timer by 2 s on full open/close (optional)
    tilt_step_count:      7     # number of discrete tilt steps (default 7, optional)

  - platform: warema_ewfs
    name: Living Room
    unique_id: warema_living_room

    btn_open:      button.living_room_shutter_open
    btn_close:     button.living_room_shutter_close
    btn_stop:      button.living_room_shutter_stop
    btn_tilt_up:   button.living_room_shutter_tilt_up
    btn_tilt_down: button.living_room_shutter_tilt_down

    travel_time_up:      24
    travel_time_down:    26
    tilt_step_time_up:    0.30
    tilt_step_time_down:  0.35
    send_stop_after_move: true
    simulate_stop_delay:  3.0

  # ── Fan-out group ─────────────────────────────────────────────────────────
  - platform: warema_ewfs
    name: Downstairs Group
    unique_id: warema_downstairs_group
    is_group: true
    command_delay: 0.5        # stagger commands to reduce simultaneous RF collisions
    group_members:
      - cover.kitchen
      - cover.living_room

  # ── Native remote group ───────────────────────────────────────────────────
  - platform: warema_ewfs
    name: Ground Floor Native Group
    unique_id: warema_ground_floor_native
    is_native_group: true
    group_members:
      - cover.kitchen
      - cover.living_room

    btn_open:      button.ground_floor_open
    btn_close:     button.ground_floor_close
    btn_stop:      button.ground_floor_stop
    btn_tilt_up:   button.ground_floor_tilt_up
    btn_tilt_down: button.ground_floor_tilt_down
```

</details>

---

## Configuration Reference

### Single Shutter

#### Required

| Key | Description |
|---|---|
| `btn_open` | Entity ID of the *open* button |
| `btn_close` | Entity ID of the *close* button |
| `btn_stop` | Entity ID of the *stop* button |
| `btn_tilt_up` | Entity ID of the *tilt up* button |
| `btn_tilt_down` | Entity ID of the *tilt down* button |

#### Optional

| Key | Default | Description |
|---|---|---|
| `travel_time_up` | — | Seconds from 0 % to 100 % |
| `travel_time_down` | — | Seconds from 100 % to 0 % |
| `tilt_step_time_up` | — | Seconds per tilt step toward 100 % |
| `tilt_step_time_down` | — | Seconds per tilt step toward 0 % |
| `send_stop_after_move` | `true` | Send `btn_stop` when a position move reaches its target |
| `simulate_stop_delay` | `0.0` | Seconds after a simulated move completes before a hardware stop is sent (0 = disabled) |
| `end_stop_buffer` | `0.0` | Extra seconds added to the stop timer when moving to fully open (100 %) or fully closed (0 %); the motor's physical end-stop cuts off automatically, so the overrun is harmless — use this to correct accumulated timing drift on every full travel (0 = disabled) |
| `tilt_step_count` | `7` | Number of discrete tilt positions (2–20). Default of `7` matches Warema EWFS shutters (~16 ° per step). Adjust for other models or manufacturers. |
| `unique_id` | — | Recommended; enables entity renaming and registry management |

### Fan-out Group

| Key | Default | Description |
|---|---|---|
| `is_group` | `false` | Set to `true` to create a fan-out group |
| `group_members` | — | List of single-shutter `cover` entity IDs |
| `command_delay` | `0` | Seconds between commands sent to successive members |

Commands are forwarded to each member cover so that individual position/tilt tracking
stays accurate.  Only `warema_ewfs` single-cover entities are accepted; others are
ignored with a warning.

### Native Remote Group

| Key | Description |
|---|---|
| `is_native_group: true` | Marks this as a native group |
| `group_members` | List of member `cover` entity IDs (for state sync) |
| `btn_open` … `btn_tilt_down` | Shared group command buttons |

Behaviour:
- Only fully open (`100 %`) and fully closed (`0 %`) are supported for cover position;
  intermediate targets are snapped to full open/close.
- Travel time is derived from the longest member travel time.
- Tilt is fully supported via repeated tilt commands.

---

## Physical Remote Co-existence

### Direction Lock

WAREMA motors have a direction lock: after moving in one direction **without a stop**,
the motor needs either a stop or a double-press of the opposite direction before it
can reverse.

- When **this integration** moves a cover it always ends with a stop, leaving the motor
  in a neutral state.
- When a **human uses the physical remote** without pressing stop, the motor stays
  direction-locked.  If an ESPHome automation then calls `simulate_command`, the tracked
  state is updated but no hardware stop is sent, so the lock persists.

### `simulate_stop_delay`

Set `simulate_stop_delay` to a small positive value (e.g. `1.0`–`3.0` s) to
automatically send a hardware stop after a simulated move finishes:

```yaml
simulate_stop_delay: 3.0   # send stop 3 s after tracking says the cover has stopped
```

The delay gives the motor time to physically come to rest before the neutralising
stop is sent.  The timer is cancelled automatically if the cover stops for any other
reason (explicit stop, new move started).

---

## End-Stop Buffer

Because position is tracked by elapsed time, a slightly under-estimated `travel_time_up`
or `travel_time_down` causes the integration to send a stop command before the cover has
physically reached the end-stop.  Over time this leads to accumulated drift.

`end_stop_buffer` adds extra seconds to the stop timer **only when the target is fully
open (100 %) or fully closed (0 %)**.  The motor has a physical end-stop in both
directions and cuts off automatically when it arrives there, so any overrun is completely
harmless.

```yaml
end_stop_buffer: 2.0   # wait up to 2 s extra before sending stop on full open/close
```

**How position tracking is affected:**
- The position estimate continues to interpolate linearly until the cover reaches the
  target, using the configured `travel_time_*`.  During the buffer window the tracked
  position is capped at 0 % / 100 % (the motor should already be at the end-stop).
- If the cover is stopped manually during the buffer window, the position estimate is
  accurate for stops that happen before `travel_time_*` elapses; once the tracking time
  has expired the position shows the target value.
- Every full open/close effectively **resets accumulated drift** back to zero.

> **Tip:** Start with a value equal to 5–10 % of your `travel_time` (e.g. `2.0` for a
> 22 s travel time) and reduce if the motor overshoots noticeably.

---

## Custom Services

### `warema_ewfs.simulate_command`

Update the integration's tracked state as if a physical remote sent the command.
No hardware button is pressed.  Use this from ESPHome automations to keep HA in sync
after a wall-remote press.

```yaml
service: warema_ewfs.simulate_command
target:
  entity_id: cover.kitchen
data:
  command: close   # open | close | stop
```

### `cover.set_cover_position_and_tilt`

Move to a target position and set the slat tilt angle in one action.  The integration
first moves to the requested position, then adjusts tilt from the direction-implied
base orientation (upward move → slats horizontal `100 %`; downward move → slats
vertical `0 %`).

```yaml
service: cover.set_cover_position_and_tilt
target:
  entity_id: cover.kitchen
data:
  position: 50
  tilt_position: 67
```

### `cover.set_cover_position_and_tilt_step`

Same as above but using a discrete tilt step index instead of a percentage.
The valid range is `0` to `tilt_step_count − 1` (default `0`–`6`).
Values above the configured maximum are clamped to the last step.

Default tilt step map (7 steps):

| Step | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| Tilt % | 0 | 17 | 33 | 50 | 67 | 83 | 100 |

Example with a 5-step cover (`tilt_step_count: 5`):

| Step | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Tilt % | 0 | 25 | 50 | 75 | 100 |

```yaml
service: cover.set_cover_position_and_tilt_step
target:
  entity_id: cover.kitchen
data:
  position: 50
  tilt_step: 4    # step 4 of 7 ≈ 67 % with default step count
```

### `warema_ewfs.force_move`

When tracked state drifts from the physical state (e.g. after manual remote use),
normal `open`/`close` commands may be skipped because the integration believes the
cover is already at the target.  `force_move` bypasses that check, always sends the
hardware command, and runs a full travel-time tracking cycle to re-sync the state.

```yaml
service: warema_ewfs.force_move
target:
  entity_id: cover.kitchen
data:
  command: close   # open | close
```

Works on single shutters, fan-out groups, and native remote groups.

### Other Services

| Service | Description |
|---|---|
| `warema_ewfs.send_command` | Send a named command (`open`, `close`, `stop`, `tilt_up`, `tilt_down`) |
| `warema_ewfs.simulate_set_tilt_position` | Update tilt state without sending a hardware command |

---

## Calibration Tips

- Measure `travel_time_up` and `travel_time_down` **separately** for each shutter
  (motors are not symmetric).
- For tilt timing, press *tilt up* once, wait, observe the angle, and adjust
  `tilt_step_time_up` until a single step moves the expected angle.
  With the default `tilt_step_count: 7` that is roughly 16 ° per step.
- Add a small `end_stop_buffer` (e.g. `2.0` for a 22 s travel time) to ensure the
  cover always reaches its physical end-stop on full open/close, resetting any
  accumulated timing drift.
- Without physical feedback, position is estimated from elapsed time — performing
  a full open or close periodically resets accumulated drift to zero.
- Manual remote usage introduces drift until HA sends a new command.
- **Other manufacturers / models:** if your cover has a different number of slat steps,
  set `tilt_step_count` accordingly (e.g. `5` for a 5-position slat mechanism).

---

## Contributing

For development setup, tooling, pre-commit hooks, and CI details see [DEVELOPMENT.md](DEVELOPMENT.md).

Issues and pull requests are welcome at the [GitHub repository](https://github.com/53RT/ha-ewfs-blinds).
