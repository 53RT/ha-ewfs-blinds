"""Cover platform for Warema EWFS shutters using ESPHome button entities."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_KNOWN_POSITION,
    ATTR_KNOWN_TILT_POSITION,
    CONF_BTN_CLOSE,
    CONF_BTN_OPEN,
    CONF_BTN_STOP,
    CONF_BTN_TILT_DOWN,
    CONF_BTN_TILT_UP,
    CONF_COMMAND_DELAY,
    CONF_GROUP_MEMBERS,
    CONF_IS_GROUP,
    CONF_IS_NATIVE_GROUP,
    CONF_SEND_STOP_AFTER_MOVE,
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_NAME,
    DEFAULT_SEND_STOP_AFTER_MOVE,
    DEFAULT_TILT_STEP_TIME_DOWN,
    DEFAULT_TILT_STEP_TIME_UP,
    DEFAULT_TRAVEL_TIME_DOWN,
    DEFAULT_TRAVEL_TIME_UP,
    DOMAIN,
    TILT_STEP_COUNT,
)
from .model import (
    clamp_percent,
    compute_cover_duration,
    infer_tilt_after_cover_move,
    should_send_auto_stop,
    snap_to_tilt_step,
    tilt_percent_to_step,
    tilt_step_to_percent,
)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_POSITION_AND_TILT = "set_cover_position_and_tilt"
SERVICE_SET_POSITION_AND_TILT_STEP = "set_cover_position_and_tilt_step"
SERVICE_SIMULATE_COMMAND = "simulate_command"
SERVICE_SIMULATE_SET_TILT = "simulate_set_tilt_position"
SERVICE_FORCE_MOVE = "force_move"
ATTR_COMMAND = "command"
ATTR_TILT_STEP = "tilt_step"

MOVE_UPDATE_INTERVAL = timedelta(milliseconds=500)
_LOGGER = logging.getLogger(__name__)
_SERVICES_REGISTERED_KEY = f"{DOMAIN}_services_registered"

SINGLE_SHUTTER_SCHEMA = {
    vol.Required(CONF_BTN_OPEN): cv.entity_id,
    vol.Required(CONF_BTN_CLOSE): cv.entity_id,
    vol.Required(CONF_BTN_STOP): cv.entity_id,
    vol.Required(CONF_BTN_TILT_UP): cv.entity_id,
    vol.Required(CONF_BTN_TILT_DOWN): cv.entity_id,
    vol.Optional(CONF_TRAVEL_TIME_UP, default=DEFAULT_TRAVEL_TIME_UP): vol.All(
        vol.Coerce(float), vol.Range(min=0.1, max=600)
    ),
    vol.Optional(CONF_TRAVEL_TIME_DOWN, default=DEFAULT_TRAVEL_TIME_DOWN): vol.All(
        vol.Coerce(float), vol.Range(min=0.1, max=600)
    ),
    vol.Optional(CONF_TILT_STEP_TIME_UP, default=DEFAULT_TILT_STEP_TIME_UP): vol.All(
        vol.Coerce(float), vol.Range(min=0.01, max=60)
    ),
    vol.Optional(CONF_TILT_STEP_TIME_DOWN, default=DEFAULT_TILT_STEP_TIME_DOWN): vol.All(
        vol.Coerce(float), vol.Range(min=0.01, max=60)
    ),
    vol.Optional(CONF_SEND_STOP_AFTER_MOVE, default=DEFAULT_SEND_STOP_AFTER_MOVE): cv.boolean,
}

GROUP_SCHEMA = {
    vol.Required(CONF_GROUP_MEMBERS): vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Optional(CONF_COMMAND_DELAY, default=DEFAULT_COMMAND_DELAY): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=60)
    ),
}

NATIVE_GROUP_SCHEMA = {
    vol.Required(CONF_GROUP_MEMBERS): vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Required(CONF_BTN_OPEN): cv.entity_id,
    vol.Required(CONF_BTN_CLOSE): cv.entity_id,
    vol.Required(CONF_BTN_STOP): cv.entity_id,
    vol.Required(CONF_BTN_TILT_UP): cv.entity_id,
    vol.Required(CONF_BTN_TILT_DOWN): cv.entity_id,
    vol.Optional(CONF_TRAVEL_TIME_UP, default=DEFAULT_TRAVEL_TIME_UP): vol.All(
        vol.Coerce(float), vol.Range(min=0.1, max=600)
    ),
    vol.Optional(CONF_TRAVEL_TIME_DOWN, default=DEFAULT_TRAVEL_TIME_DOWN): vol.All(
        vol.Coerce(float), vol.Range(min=0.1, max=600)
    ),
    vol.Optional(CONF_TILT_STEP_TIME_UP, default=DEFAULT_TILT_STEP_TIME_UP): vol.All(
        vol.Coerce(float), vol.Range(min=0.01, max=60)
    ),
    vol.Optional(CONF_TILT_STEP_TIME_DOWN, default=DEFAULT_TILT_STEP_TIME_DOWN): vol.All(
        vol.Coerce(float), vol.Range(min=0.01, max=60)
    ),
    vol.Optional(CONF_SEND_STOP_AFTER_MOVE, default=DEFAULT_SEND_STOP_AFTER_MOVE): cv.boolean,
}


def _validate_platform_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate either single-shutter or group config."""
    if config[CONF_IS_GROUP] and config[CONF_IS_NATIVE_GROUP]:
        raise vol.Invalid("Use either is_group or is_native_group, not both.")
    if config[CONF_IS_NATIVE_GROUP]:
        return vol.Schema(NATIVE_GROUP_SCHEMA, extra=vol.ALLOW_EXTRA)(config)
    if config[CONF_IS_GROUP]:
        return vol.Schema(GROUP_SCHEMA, extra=vol.ALLOW_EXTRA)(config)
    return vol.Schema(SINGLE_SHUTTER_SCHEMA, extra=vol.ALLOW_EXTRA)(config)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_IS_GROUP, default=False): cv.boolean,
        vol.Optional(CONF_IS_NATIVE_GROUP, default=False): cv.boolean,
        vol.Optional(CONF_GROUP_MEMBERS): vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional(CONF_BTN_OPEN): cv.entity_id,
        vol.Optional(CONF_BTN_CLOSE): cv.entity_id,
        vol.Optional(CONF_BTN_STOP): cv.entity_id,
        vol.Optional(CONF_BTN_TILT_UP): cv.entity_id,
        vol.Optional(CONF_BTN_TILT_DOWN): cv.entity_id,
        vol.Optional(CONF_TRAVEL_TIME_UP): vol.Coerce(float),
        vol.Optional(CONF_TRAVEL_TIME_DOWN): vol.Coerce(float),
        vol.Optional(CONF_TILT_STEP_TIME_UP): vol.Coerce(float),
        vol.Optional(CONF_TILT_STEP_TIME_DOWN): vol.Coerce(float),
        vol.Optional(CONF_SEND_STOP_AFTER_MOVE): cv.boolean,
        vol.Optional(CONF_COMMAND_DELAY): vol.Coerce(float),
    }
)
PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA, _validate_platform_config)


def _is_valid_warema_single_member(
    hass: HomeAssistant,
    entity_id: str,
    registry: er.EntityRegistry,
) -> bool:
    """Return True if entity is a Warema EWFS single-cover entity."""
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)

    if state is not None:
        if state.attributes.get("is_group") is True:
            return False
        if state.attributes.get("integration") not in (None, DOMAIN):
            return False

    if entry is not None:
        return entry.domain == "cover" and entry.platform == DOMAIN

    return state is not None and state.attributes.get("integration") == DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up Warema EWFS cover entities from YAML configuration."""
    _setup_cover_entity(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warema EWFS cover entities from a config entry."""
    config: dict[str, Any] = {**entry.data, **entry.options}
    config.setdefault(CONF_IS_GROUP, False)
    config.setdefault(CONF_IS_NATIVE_GROUP, False)
    config.setdefault(CONF_TRAVEL_TIME_UP, DEFAULT_TRAVEL_TIME_UP)
    config.setdefault(CONF_TRAVEL_TIME_DOWN, DEFAULT_TRAVEL_TIME_DOWN)
    config.setdefault(CONF_TILT_STEP_TIME_UP, DEFAULT_TILT_STEP_TIME_UP)
    config.setdefault(CONF_TILT_STEP_TIME_DOWN, DEFAULT_TILT_STEP_TIME_DOWN)
    config.setdefault(CONF_SEND_STOP_AFTER_MOVE, DEFAULT_SEND_STOP_AFTER_MOVE)
    config.setdefault(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY)
    config[CONF_UNIQUE_ID] = entry.entry_id
    _setup_cover_entity(hass, config, async_add_entities)


def _setup_cover_entity(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the correct cover entity and register platform services once."""
    entity: WaremaEWFSCover | WaremaEWFSGroupCover | WaremaEWFSNativeGroupCover
    if config[CONF_IS_NATIVE_GROUP]:
        entity = WaremaEWFSNativeGroupCover(hass, config)
    elif config[CONF_IS_GROUP]:
        entity = WaremaEWFSGroupCover(hass, config)
    else:
        entity = WaremaEWFSCover(hass, config)
    async_add_entities([entity])

    if not hass.data.get(_SERVICES_REGISTERED_KEY):
        hass.data[_SERVICES_REGISTERED_KEY] = True
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            SERVICE_SEND_COMMAND,
            {vol.Required(ATTR_COMMAND): vol.In(["open", "close", "stop", "tilt_up", "tilt_down"])},
            "async_send_named_command",
        )
        platform.async_register_entity_service(
            SERVICE_SET_POSITION_AND_TILT,
            {
                vol.Required(ATTR_POSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(ATTR_TILT_POSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            },
            "async_set_cover_position_and_tilt",
        )
        platform.async_register_entity_service(
            SERVICE_SET_POSITION_AND_TILT_STEP,
            {
                vol.Required(ATTR_POSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                vol.Required(ATTR_TILT_STEP): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=0, max=TILT_STEP_COUNT - 1),
                ),
            },
            "async_set_cover_position_and_tilt_step",
        )
        platform.async_register_entity_service(
            SERVICE_SIMULATE_COMMAND,
            {vol.Required(ATTR_COMMAND): vol.In(["open", "close", "stop", "tilt_up", "tilt_down"])},
            "async_simulate_command",
        )
        platform.async_register_entity_service(
            SERVICE_SIMULATE_SET_TILT,
            {vol.Required(ATTR_TILT_POSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=100))},
            "async_simulate_set_tilt_position",
        )
        platform.async_register_entity_service(
            SERVICE_FORCE_MOVE,
            {vol.Required(ATTR_COMMAND): vol.In(["open", "close"])},
            "async_force_move",
        )


class WaremaEWFSCover(CoverEntity, RestoreEntity):
    """Representation of one EWFS shutter controlled via button.press."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

        self._travel_time_up: float = config[CONF_TRAVEL_TIME_UP]
        self._travel_time_down: float = config[CONF_TRAVEL_TIME_DOWN]
        self._tilt_step_time_up: float = config[CONF_TILT_STEP_TIME_UP]
        self._tilt_step_time_down: float = config[CONF_TILT_STEP_TIME_DOWN]
        self._send_stop_after_move: bool = config[CONF_SEND_STOP_AFTER_MOVE]

        self._commands: dict[str, str] = {
            "open": config[CONF_BTN_OPEN],
            "close": config[CONF_BTN_CLOSE],
            "stop": config[CONF_BTN_STOP],
            "tilt_up": config[CONF_BTN_TILT_UP],
            "tilt_down": config[CONF_BTN_TILT_DOWN],
        }

        self._current_cover_position: int = 0
        self._current_tilt_position: int = 0
        self._known_position = False
        self._known_tilt_position = False

        self._move_direction: str | None = None
        self._move_started_at: float | None = None
        self._move_duration: float = 0.0
        self._move_start_pos: int = 0
        self._move_target_pos: int = 0

        self._tilt_direction: str | None = None
        self._tilt_started_at: float | None = None
        self._tilt_duration: float = 0.0
        self._tilt_start_pos: int = 0
        self._tilt_target_pos: int = 0

        self._unsub_move_timer: Callable[[], None] | None = None
        self._unsub_tilt_timer: Callable[[], None] | None = None
        self._unsub_interval: Callable[[], None] | None = None

    @property
    def supported_features(self) -> CoverEntityFeature:
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def current_cover_position(self) -> int | None:
        self._refresh_estimates()
        return self._current_cover_position if self._known_position else None

    @property
    def current_cover_tilt_position(self) -> int | None:
        self._refresh_estimates()
        return self._current_tilt_position if self._known_tilt_position else None

    @property
    def is_opening(self) -> bool | None:
        return self._move_direction == "opening"

    @property
    def is_closing(self) -> bool | None:
        return self._move_direction == "closing"

    @property
    def is_closed(self) -> bool | None:
        if not self._known_position:
            return None
        return self._current_cover_position == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            ATTR_KNOWN_POSITION: self._known_position,
            ATTR_KNOWN_TILT_POSITION: self._known_tilt_position,
            "tilt_steps": TILT_STEP_COUNT,
            "integration": DOMAIN,
            "is_group": False,
            "travel_time_up": self._travel_time_up,
            "travel_time_down": self._travel_time_down,
            "tilt_step_time_up": self._tilt_step_time_up,
            "tilt_step_time_down": self._tilt_step_time_down,
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state if available."""
        if (last_state := await self.async_get_last_state()) is not None:
            if (position := last_state.attributes.get(ATTR_POSITION)) is not None:
                self._current_cover_position = clamp_percent(float(str(position)))
                self._known_position = True
            if (tilt := last_state.attributes.get(ATTR_TILT_POSITION)) is not None:
                self._current_tilt_position = snap_to_tilt_step(int(float(str(tilt))), TILT_STEP_COUNT)
                self._known_tilt_position = True

        if not self._known_position:
            self._current_cover_position = 0
        if not self._known_tilt_position:
            self._current_tilt_position = 0

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_timers()

    async def async_open_cover(self, **kwargs: Any) -> None:
        self._known_position = True
        await self._start_cover_move(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        self._known_position = True
        await self._start_cover_move(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = clamp_percent(float(kwargs[ATTR_POSITION]))
        self._known_position = True
        await self._start_cover_move(target)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        self._refresh_estimates()
        if self._move_direction == "opening":
            self._current_tilt_position = 100
            self._known_tilt_position = True
        elif self._move_direction == "closing":
            self._current_tilt_position = 0
            self._known_tilt_position = True
        await self._send_command("stop")
        self._stop_cover_tracking()
        self.async_write_ha_state()

    #    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
    #        self._known_tilt_position = True
    #        await self._start_tilt_move(100)

    #    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
    #        self._known_tilt_position = True
    #        await self._start_tilt_move(0)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        self._known_tilt_position = True
        current_step = tilt_percent_to_step(self._current_tilt_position, TILT_STEP_COUNT)
        next_step = min(current_step + 1, TILT_STEP_COUNT - 1)
        target = tilt_step_to_percent(next_step, TILT_STEP_COUNT)
        await self._start_tilt_move(target)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        self._known_tilt_position = True
        current_step = tilt_percent_to_step(self._current_tilt_position, TILT_STEP_COUNT)
        next_step = max(current_step - 1, 0)
        target = tilt_step_to_percent(next_step, TILT_STEP_COUNT)
        await self._start_tilt_move(target)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        requested = clamp_percent(float(kwargs[ATTR_TILT_POSITION]))
        target = snap_to_tilt_step(requested, TILT_STEP_COUNT)
        self._known_tilt_position = True
        await self._start_tilt_move(target)

    async def async_set_cover_position_and_tilt(
        self,
        position: float,
        tilt_position: float,
    ) -> None:
        """Move to a cover position first and then set tilt."""
        target_position = clamp_percent(position)
        target_tilt = snap_to_tilt_step(clamp_percent(tilt_position), TILT_STEP_COUNT)

        self._refresh_estimates()
        start_position = self._current_cover_position
        start_tilt = self._current_tilt_position
        move_duration = compute_cover_duration(
            start_position,
            target_position,
            self._travel_time_up,
            self._travel_time_down,
        )

        self._known_position = True
        if move_duration > 0:
            await self._start_cover_move(target_position)
            await asyncio.sleep(move_duration + 0.05)

            self._current_tilt_position = infer_tilt_after_cover_move(
                current_position=start_position,
                target_position=target_position,
                current_tilt=start_tilt,
            )
            self._known_tilt_position = True
            self.async_write_ha_state()

        await self.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: target_tilt})

    async def async_set_cover_position_and_tilt_step(
        self,
        position: float,
        tilt_step: int,
    ) -> None:
        """Move to a cover position and then set tilt by discrete step."""
        target_tilt = tilt_step_to_percent(tilt_step, TILT_STEP_COUNT)
        await self.async_set_cover_position_and_tilt(position=position, tilt_position=target_tilt)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        self._refresh_estimates()
        await self._send_command("stop")
        self._stop_tilt_tracking()
        self.async_write_ha_state()

    async def async_send_named_command(self, command: str) -> None:
        """Expose raw command sending through an entity service."""
        await self._send_command(command)

    async def async_simulate_command(self, command: str) -> None:
        """Update position as if a command was received, without sending anything."""
        if command == "open":
            self._known_position = True
            await self._simulate_cover_move(100)
        elif command == "close":
            self._known_position = True
            await self._simulate_cover_move(0)
        elif command == "stop":
            self._refresh_estimates()
            if self._move_direction == "opening":
                self._current_tilt_position = 100
                self._known_tilt_position = True
            elif self._move_direction == "closing":
                self._current_tilt_position = 0
                self._known_tilt_position = True
            self._stop_cover_tracking()
            self._stop_tilt_tracking()
            self.async_write_ha_state()
        elif command == "tilt_up":
            self._known_tilt_position = True
            await self._simulate_tilt_move(100)
        elif command == "tilt_down":
            self._known_tilt_position = True
            await self._simulate_tilt_move(0)

    async def _simulate_cover_move(self, target: int) -> None:
        """Start position tracking toward target without sending a hardware command."""
        self._refresh_estimates()
        target = clamp_percent(target)
        duration = compute_cover_duration(
            self._current_cover_position,
            target,
            self._travel_time_up,
            self._travel_time_down,
        )
        if duration <= 0:
            return

        direction = "open" if target > self._current_cover_position else "close"
        self._move_direction = "opening" if direction == "open" else "closing"
        self._move_started_at = time.monotonic()
        self._move_duration = duration
        self._move_start_pos = self._current_cover_position
        self._move_target_pos = target

        self._schedule_cover_stop(duration)
        self._ensure_interval_listener()
        self.async_write_ha_state()

    async def _simulate_tilt_move(self, target: int) -> None:
        """Start tilt tracking toward target without sending a hardware command."""
        target = snap_to_tilt_step(target, TILT_STEP_COUNT)
        start_step = tilt_percent_to_step(self._current_tilt_position, TILT_STEP_COUNT)
        target_step = tilt_percent_to_step(target, TILT_STEP_COUNT)
        if start_step == target_step:
            return

        step_sign = 1 if target_step > start_step else -1
        next_step = start_step + step_sign
        self._current_tilt_position = tilt_step_to_percent(next_step, TILT_STEP_COUNT)
        self._known_tilt_position = True
        self.async_write_ha_state()

    async def async_simulate_set_tilt_position(self, tilt_position: float) -> None:
        """Set tilt position directly without sending any hardware commands."""
        target = snap_to_tilt_step(clamp_percent(tilt_position), TILT_STEP_COUNT)
        self._current_tilt_position = target
        self._known_tilt_position = True
        self.async_write_ha_state()

    async def async_force_move(self, command: str) -> None:
        """Force open/close regardless of tracked state."""
        self._known_position = True
        target = 100 if command == "open" else 0
        # Force-set tilt immediately: open → slats horizontal (100), close → vertical (0)
        self._current_tilt_position = target
        self._known_tilt_position = True
        await self._start_cover_move(target, force=True)

    async def _start_cover_move(self, target: int, force: bool = False) -> None:
        self._refresh_estimates()
        target = clamp_percent(target)
        duration = compute_cover_duration(
            self._current_cover_position,
            target,
            self._travel_time_up,
            self._travel_time_down,
        )
        if duration <= 0 and not force:
            return

        direction = "open" if target > self._current_cover_position else "close"
        if duration <= 0:
            # Force mode: full travel time in the target direction
            duration = self._travel_time_up if target >= 50 else self._travel_time_down
            direction = "open" if target >= 50 else "close"
        await self._send_command(direction)

        self._move_direction = "opening" if direction == "open" else "closing"
        self._move_started_at = time.monotonic()
        self._move_duration = duration
        self._move_start_pos = self._current_cover_position
        self._move_target_pos = target

        self._schedule_cover_stop(duration)
        self._ensure_interval_listener()
        self.async_write_ha_state()

    async def _start_tilt_move(self, target: int) -> None:
        target = snap_to_tilt_step(target, TILT_STEP_COUNT)
        start_step = tilt_percent_to_step(self._current_tilt_position, TILT_STEP_COUNT)
        target_step = tilt_percent_to_step(target, TILT_STEP_COUNT)
        if start_step == target_step:
            return

        direction = "tilt_up" if target_step > start_step else "tilt_down"
        step_delay = self._tilt_step_time_up if direction == "tilt_up" else self._tilt_step_time_down
        step_delta = abs(target_step - start_step)
        step_sign = 1 if target_step > start_step else -1

        for index in range(step_delta):
            await self._send_command(direction)
            current_step = start_step + ((index + 1) * step_sign)
            self._current_tilt_position = tilt_step_to_percent(current_step, TILT_STEP_COUNT)
            self._known_tilt_position = True
            self.async_write_ha_state()
            if index < step_delta - 1:
                await asyncio.sleep(step_delay)

    async def _send_command(self, command: str) -> None:
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": self._commands[command]},
            blocking=True,
        )

    def _schedule_cover_stop(self, duration: float) -> None:
        if self._unsub_move_timer:
            self._unsub_move_timer()

        @callback
        def _on_cover_timer(_: Any) -> None:
            self.hass.async_create_task(self._finish_cover_move())

        self._unsub_move_timer = async_call_later(self.hass, duration, _on_cover_timer)

    def _schedule_tilt_stop(self, duration: float) -> None:
        if self._unsub_tilt_timer:
            self._unsub_tilt_timer()

        @callback
        def _on_tilt_timer(_: Any) -> None:
            self.hass.async_create_task(self._finish_tilt_move())

        self._unsub_tilt_timer = async_call_later(self.hass, duration, _on_tilt_timer)

    async def _finish_cover_move(self) -> None:
        inferred_tilt = infer_tilt_after_cover_move(
            current_position=self._move_start_pos,
            target_position=self._move_target_pos,
            current_tilt=self._current_tilt_position,
        )
        self._current_cover_position = self._move_target_pos
        self._known_position = True
        self._current_tilt_position = inferred_tilt
        self._known_tilt_position = True
        self._stop_cover_tracking()
        if should_send_auto_stop(self._send_stop_after_move, is_tilt_move=False):
            await self._send_command("stop")
        self.async_write_ha_state()

    async def _finish_tilt_move(self) -> None:
        self._current_tilt_position = self._tilt_target_pos
        self._known_tilt_position = True
        self._stop_tilt_tracking()
        self.async_write_ha_state()

    def _refresh_estimates(self) -> None:
        now = time.monotonic()

        if self._move_direction and self._move_started_at is not None and self._move_duration > 0:
            elapsed = min(now - self._move_started_at, self._move_duration)
            progress = elapsed / self._move_duration
            delta = self._move_target_pos - self._move_start_pos
            self._current_cover_position = clamp_percent(self._move_start_pos + (delta * progress))

        if self._tilt_direction and self._tilt_started_at is not None and self._tilt_duration > 0:
            elapsed = min(now - self._tilt_started_at, self._tilt_duration)
            progress = elapsed / self._tilt_duration
            delta = self._tilt_target_pos - self._tilt_start_pos
            estimated = self._tilt_start_pos + (delta * progress)
            self._current_tilt_position = snap_to_tilt_step(int(round(estimated)), TILT_STEP_COUNT)

    def _stop_cover_tracking(self) -> None:
        self._move_direction = None
        self._move_started_at = None
        self._move_duration = 0.0
        if self._unsub_move_timer:
            self._unsub_move_timer()
            self._unsub_move_timer = None
        self._cleanup_interval_listener()

    def _stop_tilt_tracking(self) -> None:
        self._tilt_direction = None
        self._tilt_started_at = None
        self._tilt_duration = 0.0
        if self._unsub_tilt_timer:
            self._unsub_tilt_timer()
            self._unsub_tilt_timer = None
        self._cleanup_interval_listener()

    def _cancel_timers(self) -> None:
        self._stop_cover_tracking()
        self._stop_tilt_tracking()

    @callback
    def _ensure_interval_listener(self) -> None:
        if self._unsub_interval is None:
            self._unsub_interval = async_track_time_interval(
                self.hass,
                self._async_tick,
                MOVE_UPDATE_INTERVAL,
            )

    @callback
    def _cleanup_interval_listener(self) -> None:
        if self._move_direction or self._tilt_direction:
            return
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def _async_tick(self, _now) -> None:
        self._refresh_estimates()
        self.async_write_ha_state()


class WaremaEWFSGroupCover(CoverEntity):
    """Group cover that fans out commands to member cover entities.

    Position and tilt state are intentionally not tracked on the group level because
    individual member shutters can be moved independently, making group-level state
    impossible to keep in sync.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)
        self._configured_members: list[str] = list(config[CONF_GROUP_MEMBERS])
        self._members: list[str] = []
        self._invalid_members: list[str] = []
        self._command_delay: float = config.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY)

    @property
    def supported_features(self) -> CoverEntityFeature:
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        return None

    @property
    def is_closed(self) -> bool | None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "tilt_steps": TILT_STEP_COUNT,
            "integration": DOMAIN,
            "is_group": True,
            "group_members": self._configured_members,
            "valid_group_members": self._members,
            "invalid_group_members": self._invalid_members,
        }

    async def async_added_to_hass(self) -> None:
        self._revalidate_group_members(log_warning=True)

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._fanout("open_cover")

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._fanout("close_cover")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = clamp_percent(float(kwargs[ATTR_POSITION]))
        await self._fanout("set_cover_position", {ATTR_POSITION: target})

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._fanout("stop_cover")

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._fanout("open_cover_tilt")

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._fanout("close_cover_tilt")

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        target = snap_to_tilt_step(clamp_percent(float(kwargs[ATTR_TILT_POSITION])), TILT_STEP_COUNT)
        await self._fanout("set_cover_tilt_position", {ATTR_TILT_POSITION: target})

    async def async_set_cover_position_and_tilt(
        self,
        position: float,
        tilt_position: float,
    ) -> None:
        target_position = clamp_percent(position)
        target_tilt = snap_to_tilt_step(clamp_percent(tilt_position), TILT_STEP_COUNT)
        await self._fanout(
            SERVICE_SET_POSITION_AND_TILT,
            {
                ATTR_POSITION: target_position,
                ATTR_TILT_POSITION: target_tilt,
            },
        )

    async def async_set_cover_position_and_tilt_step(
        self,
        position: float,
        tilt_step: int,
    ) -> None:
        target_position = clamp_percent(position)
        await self._fanout(
            SERVICE_SET_POSITION_AND_TILT_STEP,
            {
                ATTR_POSITION: target_position,
                ATTR_TILT_STEP: int(tilt_step),
            },
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        await self._fanout("stop_cover_tilt")

    async def async_send_named_command(self, command: str) -> None:
        if command == "open":
            await self.async_open_cover()
        elif command == "close":
            await self.async_close_cover()
        elif command == "stop":
            await self.async_stop_cover()
            await self.async_stop_cover_tilt()
        elif command == "tilt_up":
            await self.async_open_cover_tilt()
        elif command == "tilt_down":
            await self.async_close_cover_tilt()

    async def async_force_move(self, command: str) -> None:
        """Force open/close on all group members regardless of tracked state."""
        self._revalidate_group_members()
        if not self._members:
            _LOGGER.warning(
                "Warema EWFS group '%s' has no valid members. Check 'group_members'.",
                self.entity_id or self._attr_name,
            )
            return

        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_MOVE,
            {"entity_id": self._members, ATTR_COMMAND: command},
            blocking=True,
        )

    async def _fanout(self, service: str, extra: dict[str, Any] | None = None) -> None:
        self._revalidate_group_members()
        if not self._members:
            _LOGGER.warning(
                "Warema EWFS group '%s' has no valid members. Check 'group_members'.",
                self.entity_id or self._attr_name,
            )
            return

        if self._command_delay > 0:
            for index, member in enumerate(self._members):
                if index > 0:
                    await asyncio.sleep(self._command_delay)
                payload: dict[str, Any] = {"entity_id": member}
                if extra:
                    payload.update(extra)
                await self.hass.services.async_call("cover", service, payload, blocking=True)
        else:
            payload = {"entity_id": self._members}
            if extra:
                payload.update(extra)
            await self.hass.services.async_call("cover", service, payload, blocking=True)

    async def async_simulate_command(self, command: str) -> None:
        """Fan out simulate_command to all valid member entities."""
        self._revalidate_group_members()
        if not self._members:
            return
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SIMULATE_COMMAND,
            {"entity_id": self._members, ATTR_COMMAND: command},
            blocking=True,
        )

    def _revalidate_group_members(self, log_warning: bool = False) -> None:
        """Keep only valid Warema EWFS single-cover entities as group members."""
        registry = er.async_get(self.hass)
        valid: list[str] = []
        invalid: list[str] = []

        for entity_id in self._configured_members:
            if self._is_valid_member(entity_id, registry):
                valid.append(entity_id)
            else:
                invalid.append(entity_id)

        warn_now = log_warning or invalid != self._invalid_members
        self._members = valid
        self._invalid_members = invalid

        if warn_now and invalid:
            _LOGGER.warning(
                "Warema EWFS group '%s' ignores non-Warema members: %s",
                self.entity_id or self._attr_name,
                ", ".join(invalid),
            )

    def _is_valid_member(self, entity_id: str, registry: er.EntityRegistry) -> bool:
        """Return True if entity is a Warema EWFS single-cover entity."""
        return _is_valid_warema_single_member(self.hass, entity_id, registry)


class WaremaEWFSNativeGroupCover(WaremaEWFSCover):
    """Native remote group using dedicated group command buttons."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        super().__init__(hass, config)
        self._configured_members: list[str] = list(config[CONF_GROUP_MEMBERS])
        self._members: list[str] = []
        self._invalid_members: list[str] = []

    @property
    def supported_features(self) -> CoverEntityFeature:
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
            | CoverEntityFeature.SET_TILT_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        return None

    @property
    def is_closed(self) -> bool | None:
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        attrs.pop(ATTR_KNOWN_POSITION, None)
        attrs.pop(ATTR_KNOWN_TILT_POSITION, None)
        attrs.update(
            {
                "is_group": True,
                "group_mode": "native_remote",
                "group_members": self._configured_members,
                "valid_group_members": self._members,
                "invalid_group_members": self._invalid_members,
                "supports_intermediate_cover_positions": False,
            }
        )
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh_group_timing(log_warning=True)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        self._refresh_group_timing()
        await super().async_open_cover(**kwargs)
        await self._fanout_simulate("open")

    async def async_close_cover(self, **kwargs: Any) -> None:
        self._refresh_group_timing()
        await super().async_close_cover(**kwargs)
        await self._fanout_simulate("close")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        requested = clamp_percent(float(kwargs[ATTR_POSITION]))
        if requested not in (0, 100):
            _LOGGER.warning(
                "Native Warema group '%s' does not support intermediate cover position %s%%. Using %s%%.",
                self.entity_id or self._attr_name,
                requested,
                100 if requested >= 50 else 0,
            )

        if requested >= 50:
            await self.async_open_cover()
        else:
            await self.async_close_cover()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        self._refresh_group_timing()
        await super().async_open_cover_tilt(**kwargs)
        await self._fanout_tilt(self._current_tilt_position)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        self._refresh_group_timing()
        await super().async_close_cover_tilt(**kwargs)
        await self._fanout_tilt(self._current_tilt_position)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        self._refresh_group_timing()
        await super().async_set_cover_tilt_position(**kwargs)
        await self._fanout_tilt(self._current_tilt_position)

    async def async_set_cover_position_and_tilt(self, position: float, tilt_position: float) -> None:
        target_position = clamp_percent(position)
        await self.async_set_cover_position(**{ATTR_POSITION: target_position})
        await self.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: tilt_position})

    async def async_set_cover_position_and_tilt_step(self, position: float, tilt_step: int) -> None:
        target_tilt = tilt_step_to_percent(tilt_step, TILT_STEP_COUNT)
        await self.async_set_cover_position_and_tilt(position=position, tilt_position=target_tilt)

    async def async_force_move(self, command: str) -> None:
        """Force open/close and propagate to all group members."""
        await super().async_force_move(command)
        await self._fanout_simulate(command)

    async def _fanout_simulate(self, command: str) -> None:
        """Send simulate_command to all valid member entities."""
        self._revalidate_group_members()
        if not self._members:
            return
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SIMULATE_COMMAND,
            {"entity_id": self._members, ATTR_COMMAND: command},
            blocking=True,
        )

    async def _fanout_tilt(self, tilt_position: int) -> None:
        """Set tilt position on all valid member entities without sending hardware commands."""
        self._revalidate_group_members()
        if not self._members:
            return
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SIMULATE_SET_TILT,
            {"entity_id": self._members, ATTR_TILT_POSITION: tilt_position},
            blocking=True,
        )

    async def _start_cover_move(self, target: int, force: bool = False) -> None:
        self._refresh_estimates()
        target = clamp_percent(target)

        if target == self._current_cover_position and not force:
            return

        direction = "open" if target > self._current_cover_position else "close"
        if target == self._current_cover_position:
            # Force mode: infer direction from target value
            direction = "open" if target >= 50 else "close"
        duration = self._travel_time_up if direction == "open" else self._travel_time_down

        await self._send_command(direction)

        self._move_direction = "opening" if direction == "open" else "closing"
        self._move_started_at = time.monotonic()
        self._move_duration = duration
        self._move_start_pos = self._current_cover_position
        self._move_target_pos = 100 if direction == "open" else 0

        self._schedule_cover_stop(duration)
        self._ensure_interval_listener()
        self.async_write_ha_state()

    def _refresh_group_timing(self, log_warning: bool = False) -> None:
        self._revalidate_group_members(log_warning=log_warning)

        max_up = None
        max_down = None
        max_tilt_up = None
        max_tilt_down = None

        for entity_id in self._members:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue

            attr_up = state.attributes.get("travel_time_up")
            attr_down = state.attributes.get("travel_time_down")
            attr_tilt_up = state.attributes.get("tilt_step_time_up")
            attr_tilt_down = state.attributes.get("tilt_step_time_down")

            if isinstance(attr_up, int | float):
                max_up = max(max_up or 0.0, float(attr_up))
            if isinstance(attr_down, int | float):
                max_down = max(max_down or 0.0, float(attr_down))
            if isinstance(attr_tilt_up, int | float):
                max_tilt_up = max(max_tilt_up or 0.0, float(attr_tilt_up))
            if isinstance(attr_tilt_down, int | float):
                max_tilt_down = max(max_tilt_down or 0.0, float(attr_tilt_down))

        if max_up is not None:
            self._travel_time_up = max_up
        if max_down is not None:
            self._travel_time_down = max_down
        if max_tilt_up is not None:
            self._tilt_step_time_up = max_tilt_up
        if max_tilt_down is not None:
            self._tilt_step_time_down = max_tilt_down

    def _revalidate_group_members(self, log_warning: bool = False) -> None:
        registry = er.async_get(self.hass)
        valid: list[str] = []
        invalid: list[str] = []

        for entity_id in self._configured_members:
            if _is_valid_warema_single_member(self.hass, entity_id, registry):
                valid.append(entity_id)
            else:
                invalid.append(entity_id)

        warn_now = log_warning or invalid != self._invalid_members
        self._members = valid
        self._invalid_members = invalid

        if warn_now and invalid:
            _LOGGER.warning(
                "Native Warema group '%s' ignores non-Warema members: %s",
                self.entity_id or self._attr_name,
                ", ".join(invalid),
            )

        if log_warning and not valid:
            _LOGGER.warning(
                "Native Warema group '%s' has no valid members for travel-time derivation.",
                self.entity_id or self._attr_name,
            )
