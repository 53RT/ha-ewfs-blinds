"""Cover platform for Warema EWFS shutters using ESPHome button entities."""

from __future__ import annotations

import asyncio
import logging
import time
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
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_KNOWN_POSITION,
    ATTR_KNOWN_TILT_POSITION,
    CONF_BTN_CLOSE,
    CONF_BTN_OPEN,
    CONF_BTN_STOP,
    CONF_BTN_TILT_DOWN,
    CONF_BTN_TILT_UP,
    CONF_GROUP_MEMBERS,
    CONF_IS_GROUP,
    CONF_SHUTTER_ID,
    CONF_SEND_STOP_AFTER_MOVE,
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
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
    compute_tilt_duration,
    infer_tilt_after_cover_move,
    should_send_auto_stop,
    snap_to_tilt_step,
    tilt_step_to_percent,
)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_POSITION_AND_TILT = "set_cover_position_and_tilt"
SERVICE_SET_POSITION_AND_TILT_STEP = "set_cover_position_and_tilt_step"
ATTR_COMMAND = "command"
ATTR_TILT_STEP = "tilt_step"

MOVE_UPDATE_INTERVAL = timedelta(milliseconds=500)
_LOGGER = logging.getLogger(__name__)

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
}


def _validate_platform_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate either single-shutter or group config."""
    if config[CONF_IS_GROUP]:
        return vol.Schema(GROUP_SCHEMA, extra=vol.ALLOW_EXTRA)(config)
    return vol.Schema(SINGLE_SHUTTER_SCHEMA, extra=vol.ALLOW_EXTRA)(config)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_SHUTTER_ID): cv.string,
        vol.Optional(CONF_IS_GROUP, default=False): cv.boolean,
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
    }
)
PLATFORM_SCHEMA = vol.All(PLATFORM_SCHEMA, _validate_platform_config)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up Warema EWFS cover entities from YAML configuration."""
    entity: WaremaEWFSCover | WaremaEWFSGroupCover
    if config[CONF_IS_GROUP]:
        entity = WaremaEWFSGroupCover(hass, config)
    else:
        entity = WaremaEWFSCover(hass, config)
    async_add_entities([entity])

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


class WaremaEWFSCover(CoverEntity, RestoreEntity):
    """Representation of one EWFS shutter controlled via button.press."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)

        self._shutter_id: str = config.get(CONF_SHUTTER_ID) or self._attr_name.lower().replace(" ", "_")

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

        self._unsub_move_timer = None
        self._unsub_tilt_timer = None
        self._unsub_interval = None

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
            "shutter_id": self._shutter_id,
            "is_group": False,
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state if available."""
        if (last_state := await self.async_get_last_state()) is not None:
            if (position := last_state.attributes.get(ATTR_POSITION)) is not None:
                self._current_cover_position = clamp_percent(float(position))
                self._known_position = True
            if (tilt := last_state.attributes.get(ATTR_TILT_POSITION)) is not None:
                self._current_tilt_position = snap_to_tilt_step(int(float(tilt)), TILT_STEP_COUNT)
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
        await self._send_command("stop")
        self._stop_cover_tracking()
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        self._known_tilt_position = True
        await self._start_tilt_move(100)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        self._known_tilt_position = True
        await self._start_tilt_move(0)

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

    async def _start_cover_move(self, target: int) -> None:
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
        self._refresh_estimates()
        target = snap_to_tilt_step(target, TILT_STEP_COUNT)
        duration = compute_tilt_duration(
            self._current_tilt_position,
            target,
            self._tilt_step_time_up,
            self._tilt_step_time_down,
        )
        if duration <= 0:
            return

        direction = "tilt_up" if target > self._current_tilt_position else "tilt_down"
        await self._send_command(direction)

        self._tilt_direction = "opening" if direction == "tilt_up" else "closing"
        self._tilt_started_at = time.monotonic()
        self._tilt_duration = duration
        self._tilt_start_pos = self._current_tilt_position
        self._tilt_target_pos = target

        self._schedule_tilt_stop(duration)
        self._ensure_interval_listener()
        self.async_write_ha_state()

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
        self._current_cover_position = self._move_target_pos
        self._known_position = True
        self._stop_cover_tracking()
        if should_send_auto_stop(self._send_stop_after_move, is_tilt_move=False):
            await self._send_command("stop")
        self.async_write_ha_state()

    async def _finish_tilt_move(self) -> None:
        self._current_tilt_position = self._tilt_target_pos
        self._known_tilt_position = True
        self._stop_tilt_tracking()
        if should_send_auto_stop(self._send_stop_after_move, is_tilt_move=True):
            await self._send_command("stop")
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


class WaremaEWFSGroupCover(CoverEntity, RestoreEntity):
    """Group cover that fans out commands to member cover entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)
        self._configured_members: list[str] = list(config[CONF_GROUP_MEMBERS])
        self._members: list[str] = []
        self._invalid_members: list[str] = []
        self._shutter_id: str = config.get(CONF_SHUTTER_ID) or self._attr_name.lower().replace(" ", "_")

        self._current_cover_position: int = 0
        self._current_tilt_position: int = 0
        self._known_position = False
        self._known_tilt_position = False

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
        return self._current_cover_position if self._known_position else None

    @property
    def current_cover_tilt_position(self) -> int | None:
        return self._current_tilt_position if self._known_tilt_position else None

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
            "shutter_id": self._shutter_id,
            "is_group": True,
            "group_members": self._configured_members,
            "valid_group_members": self._members,
            "invalid_group_members": self._invalid_members,
        }

    async def async_added_to_hass(self) -> None:
        self._revalidate_group_members(log_warning=True)
        if (last_state := await self.async_get_last_state()) is not None:
            if (position := last_state.attributes.get(ATTR_POSITION)) is not None:
                self._current_cover_position = clamp_percent(float(position))
                self._known_position = True
            if (tilt := last_state.attributes.get(ATTR_TILT_POSITION)) is not None:
                self._current_tilt_position = snap_to_tilt_step(int(float(tilt)), TILT_STEP_COUNT)
                self._known_tilt_position = True

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._fanout("open_cover")
        self._current_cover_position = 100
        self._known_position = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._fanout("close_cover")
        self._current_cover_position = 0
        self._known_position = True
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        target = clamp_percent(float(kwargs[ATTR_POSITION]))
        await self._fanout("set_cover_position", {ATTR_POSITION: target})
        self._current_cover_position = target
        self._known_position = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._fanout("stop_cover")

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._fanout("open_cover_tilt")
        self._current_tilt_position = 100
        self._known_tilt_position = True
        self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._fanout("close_cover_tilt")
        self._current_tilt_position = 0
        self._known_tilt_position = True
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        target = snap_to_tilt_step(clamp_percent(float(kwargs[ATTR_TILT_POSITION])), TILT_STEP_COUNT)
        await self._fanout("set_cover_tilt_position", {ATTR_TILT_POSITION: target})
        self._current_tilt_position = target
        self._known_tilt_position = True
        self.async_write_ha_state()

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
        self._current_cover_position = target_position
        self._known_position = True
        self._current_tilt_position = target_tilt
        self._known_tilt_position = True
        self.async_write_ha_state()

    async def async_set_cover_position_and_tilt_step(
        self,
        position: float,
        tilt_step: int,
    ) -> None:
        target_position = clamp_percent(position)
        target_tilt = tilt_step_to_percent(tilt_step, TILT_STEP_COUNT)
        await self._fanout(
            SERVICE_SET_POSITION_AND_TILT_STEP,
            {
                ATTR_POSITION: target_position,
                ATTR_TILT_STEP: int(tilt_step),
            },
        )
        self._current_cover_position = target_position
        self._known_position = True
        self._current_tilt_position = target_tilt
        self._known_tilt_position = True
        self.async_write_ha_state()

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

    async def _fanout(self, service: str, extra: dict[str, Any] | None = None) -> None:
        self._revalidate_group_members()
        if not self._members:
            _LOGGER.warning(
                "Warema EWFS group '%s' has no valid members. Check 'group_members'.",
                self.entity_id or self._attr_name,
            )
            return

        payload: dict[str, Any] = {"entity_id": self._members}
        if extra:
            payload.update(extra)
        await self.hass.services.async_call("cover", service, payload, blocking=True)

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
        entry = registry.async_get(entity_id)
        state = self.hass.states.get(entity_id)

        if state is not None:
            if state.attributes.get("is_group") is True:
                return False
            if state.attributes.get("integration") not in (None, DOMAIN):
                return False

        if entry is not None:
            return entry.domain == "cover" and entry.platform == DOMAIN

        return state is not None and state.attributes.get("integration") == DOMAIN


