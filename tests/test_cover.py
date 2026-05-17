"""Tests for WaremaEWFSCover force_move and _start_cover_move logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.warema_ewfs.const import (
    CONF_BTN_CLOSE,
    CONF_BTN_OPEN,
    CONF_BTN_STOP,
    CONF_BTN_TILT_DOWN,
    CONF_BTN_TILT_UP,
    CONF_GROUP_MEMBERS,
    CONF_IS_GROUP,
    CONF_IS_NATIVE_GROUP,
    CONF_SEND_STOP_AFTER_MOVE,
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_SEND_STOP_AFTER_MOVE,
    DEFAULT_TILT_STEP_TIME_DOWN,
    DEFAULT_TILT_STEP_TIME_UP,
    DEFAULT_TRAVEL_TIME_DOWN,
    DEFAULT_TRAVEL_TIME_UP,
)
from custom_components.warema_ewfs.cover import (
    WaremaEWFSCover,
    WaremaEWFSNativeGroupCover,
)

CONF_NAME = "name"


def _make_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal single-shutter config."""
    cfg: dict[str, Any] = {
        CONF_NAME: "Test Shutter",
        CONF_IS_GROUP: False,
        CONF_IS_NATIVE_GROUP: False,
        CONF_BTN_OPEN: "button.open",
        CONF_BTN_CLOSE: "button.close",
        CONF_BTN_STOP: "button.stop",
        CONF_BTN_TILT_UP: "button.tilt_up",
        CONF_BTN_TILT_DOWN: "button.tilt_down",
        CONF_TRAVEL_TIME_UP: DEFAULT_TRAVEL_TIME_UP,
        CONF_TRAVEL_TIME_DOWN: DEFAULT_TRAVEL_TIME_DOWN,
        CONF_TILT_STEP_TIME_UP: DEFAULT_TILT_STEP_TIME_UP,
        CONF_TILT_STEP_TIME_DOWN: DEFAULT_TILT_STEP_TIME_DOWN,
        CONF_SEND_STOP_AFTER_MOVE: DEFAULT_SEND_STOP_AFTER_MOVE,
    }
    cfg.update(overrides)
    return cfg


def _make_native_group_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal native group config."""
    cfg = _make_config()
    cfg[CONF_IS_NATIVE_GROUP] = True
    cfg[CONF_GROUP_MEMBERS] = ["cover.member_a"]
    cfg.update(overrides)
    return cfg


def _make_hass() -> MagicMock:
    """Return a minimal mock of HomeAssistant."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


def _make_cover(hass: MagicMock | None = None, **config_overrides: Any) -> WaremaEWFSCover:
    """Create a WaremaEWFSCover with mocked hass and sensible defaults."""
    hass = hass or _make_hass()
    cover = WaremaEWFSCover(hass, _make_config(**config_overrides))
    cover.async_write_ha_state = MagicMock()
    return cover


def _make_native_group(hass: MagicMock | None = None, **config_overrides: Any) -> WaremaEWFSNativeGroupCover:
    """Create a WaremaEWFSNativeGroupCover with mocked hass."""
    hass = hass or _make_hass()
    cover = WaremaEWFSNativeGroupCover(hass, _make_native_group_config(**config_overrides))
    cover.async_write_ha_state = MagicMock()
    return cover


# ---------------------------------------------------------------------------
# _start_cover_move: normal behaviour (regression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_cover_move_skips_when_already_at_target():
    """Normal mode: no command when already at target position."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(0)

    cover.hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_start_cover_move_sends_command_when_not_at_target():
    """Normal mode: sends command when target differs from current position."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(100)

    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][0] == "button"
    assert call_kwargs[0][1] == "press"
    assert call_kwargs[0][2]["entity_id"] == "button.open"


# ---------------------------------------------------------------------------
# _start_cover_move: force mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_cover_move_force_sends_close_when_already_closed():
    """Force mode: sends close command even when tracked position is already 0."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(0, force=True)

    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][2]["entity_id"] == "button.close"


@pytest.mark.asyncio
async def test_start_cover_move_force_sends_open_when_already_open():
    """Force mode: sends open command even when tracked position is already 100."""
    cover = _make_cover()
    cover._current_cover_position = 100
    cover._known_position = True

    await cover._start_cover_move(100, force=True)

    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][2]["entity_id"] == "button.open"


@pytest.mark.asyncio
async def test_start_cover_move_force_uses_full_travel_time_for_close():
    """Force mode at target 0: duration equals travel_time_down."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(0, force=True)

    assert cover._move_duration == DEFAULT_TRAVEL_TIME_DOWN
    assert cover._move_direction == "closing"
    assert cover._move_target_pos == 0


@pytest.mark.asyncio
async def test_start_cover_move_force_uses_full_travel_time_for_open():
    """Force mode at target 100: duration equals travel_time_up."""
    cover = _make_cover()
    cover._current_cover_position = 100
    cover._known_position = True

    await cover._start_cover_move(100, force=True)

    assert cover._move_duration == DEFAULT_TRAVEL_TIME_UP
    assert cover._move_direction == "opening"
    assert cover._move_target_pos == 100


# ---------------------------------------------------------------------------
# async_force_move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_move_close_sets_known_position_and_sends():
    """async_force_move('close') marks position known and sends close."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = False

    await cover.async_force_move("close")

    assert cover._known_position is True
    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][2]["entity_id"] == "button.close"


@pytest.mark.asyncio
async def test_force_move_open_sets_known_position_and_sends():
    """async_force_move('open') marks position known and sends open."""
    cover = _make_cover()
    cover._current_cover_position = 100
    cover._known_position = False

    await cover.async_force_move("open")

    assert cover._known_position is True
    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][2]["entity_id"] == "button.open"


@pytest.mark.asyncio
async def test_force_move_close_when_tracked_position_already_closed():
    """async_force_move('close') sends command even when already at position 0."""
    cover = _make_cover()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover.async_force_move("close")

    cover.hass.services.async_call.assert_called_once()
    assert cover._move_direction == "closing"


@pytest.mark.asyncio
async def test_force_move_open_when_tracked_position_already_open():
    """async_force_move('open') sends command even when already at position 100."""
    cover = _make_cover()
    cover._current_cover_position = 100
    cover._known_position = True

    await cover.async_force_move("open")

    cover.hass.services.async_call.assert_called_once()
    assert cover._move_direction == "opening"


# ---------------------------------------------------------------------------
# WaremaEWFSNativeGroupCover: force mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_native_group_start_cover_move_skips_when_already_at_target():
    """Native group: no command when already at target (normal mode)."""
    cover = _make_native_group()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(0)

    cover.hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_native_group_start_cover_move_force_sends_when_at_target():
    """Native group: force sends close even when tracked at 0."""
    cover = _make_native_group()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover._start_cover_move(0, force=True)

    cover.hass.services.async_call.assert_called_once()
    call_kwargs = cover.hass.services.async_call.call_args
    assert call_kwargs[0][2]["entity_id"] == "button.close"


@pytest.mark.asyncio
async def test_native_group_force_move_close():
    """Native group async_force_move('close') sends close at position 0."""
    cover = _make_native_group()
    cover._current_cover_position = 0
    cover._known_position = True

    await cover.async_force_move("close")

    cover.hass.services.async_call.assert_called_once()
    assert cover._move_direction == "closing"


@pytest.mark.asyncio
async def test_native_group_force_move_open():
    """Native group async_force_move('open') sends open at position 100."""
    cover = _make_native_group()
    cover._current_cover_position = 100
    cover._known_position = True

    await cover.async_force_move("open")

    cover.hass.services.async_call.assert_called_once()
    assert cover._move_direction == "opening"
