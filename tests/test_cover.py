"""Tests for WaremaEWFSCover entity logic."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_CURRENT_TILT_POSITION

from custom_components.warema_ewfs.const import (
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
    CONF_SIMULATE_STOP_DELAY,
    CONF_TILT_STEP_COUNT,
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_SEND_STOP_AFTER_MOVE,
    DEFAULT_SIMULATE_STOP_DELAY,
    DEFAULT_TILT_STEP_COUNT,
    DEFAULT_TILT_STEP_TIME_DOWN,
    DEFAULT_TILT_STEP_TIME_UP,
    DEFAULT_TRAVEL_TIME_DOWN,
    DEFAULT_TRAVEL_TIME_UP,
)
from custom_components.warema_ewfs.cover import (
    ATTR_COMMAND,
    SERVICE_SIMULATE_COMMAND,
    SERVICE_SIMULATE_SET_TILT,
    WaremaEWFSCover,
    WaremaEWFSGroupCover,
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
        CONF_SIMULATE_STOP_DELAY: DEFAULT_SIMULATE_STOP_DELAY,
        CONF_TILT_STEP_COUNT: DEFAULT_TILT_STEP_COUNT,
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


def _make_native_group_with_members(
    hass: MagicMock | None = None,
    members: list[str] | None = None,
    **config_overrides: Any,
) -> WaremaEWFSNativeGroupCover:
    """Create a native group with pre-validated members (bypasses HA entity registry)."""
    cover = _make_native_group(hass=hass, **config_overrides)
    members = members or ["cover.member_a"]
    cover._configured_members = members
    cover._members = list(members)
    # Prevent _revalidate_group_members from resetting the mocked members
    cover._revalidate_group_members = MagicMock()
    return cover


def _make_group_config(command_delay: float = DEFAULT_COMMAND_DELAY, **overrides: Any) -> dict[str, Any]:
    """Return a minimal fan-out group config."""
    return {
        CONF_NAME: "Test Group",
        CONF_IS_GROUP: True,
        CONF_IS_NATIVE_GROUP: False,
        CONF_GROUP_MEMBERS: ["cover.member_a", "cover.member_b"],
        CONF_COMMAND_DELAY: command_delay,
        **overrides,
    }


def _make_group_with_members(
    hass: MagicMock | None = None,
    members: list[str] | None = None,
    command_delay: float = DEFAULT_COMMAND_DELAY,
) -> WaremaEWFSGroupCover:
    """Create a WaremaEWFSGroupCover with pre-validated members."""
    hass = hass or _make_hass()
    cfg = _make_group_config(command_delay=command_delay)
    if members:
        cfg[CONF_GROUP_MEMBERS] = members
    cover = WaremaEWFSGroupCover(hass, cfg)
    cover.async_write_ha_state = MagicMock()
    cover._configured_members = cfg[CONF_GROUP_MEMBERS]
    cover._members = list(cfg[CONF_GROUP_MEMBERS])
    cover._revalidate_group_members = MagicMock()
    return cover


def _last_button_pressed(cover: WaremaEWFSCover) -> str:
    """Return the entity_id of the last button.press call."""
    return cover.hass.services.async_call.call_args[0][2]["entity_id"]


# ===========================================================================
# Properties
# ===========================================================================


class TestProperties:
    """Test cover property behaviour."""

    def test_is_closed_true_when_position_zero(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True
        assert cover.is_closed is True

    def test_is_closed_false_when_position_nonzero(self):
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        assert cover.is_closed is False

    def test_is_closed_none_when_position_unknown(self):
        cover = _make_cover()
        cover._known_position = False
        assert cover.is_closed is None

    def test_is_opening_when_moving_up(self):
        cover = _make_cover()
        cover._move_direction = "opening"
        assert cover.is_opening is True
        assert cover.is_closing is False

    def test_is_closing_when_moving_down(self):
        cover = _make_cover()
        cover._move_direction = "closing"
        assert cover.is_closing is True
        assert cover.is_opening is False

    def test_is_opening_closing_none_when_idle(self):
        cover = _make_cover()
        cover._move_direction = None
        assert cover.is_opening is False
        assert cover.is_closing is False

    def test_current_position_none_when_unknown(self):
        cover = _make_cover()
        cover._known_position = False
        assert cover.current_cover_position is None

    def test_current_position_returns_value_when_known(self):
        cover = _make_cover()
        cover._current_cover_position = 42
        cover._known_position = True
        assert cover.current_cover_position == 42

    def test_current_tilt_none_when_unknown(self):
        cover = _make_cover()
        cover._known_tilt_position = False
        assert cover.current_cover_tilt_position is None

    def test_current_tilt_returns_value_when_known(self):
        cover = _make_cover()
        cover._current_tilt_position = 67
        cover._known_tilt_position = True
        assert cover.current_cover_tilt_position == 67

    def test_extra_state_attributes_contains_expected_keys(self):
        cover = _make_cover()
        attrs = cover.extra_state_attributes
        assert attrs["integration"] == "warema_ewfs"
        assert attrs["is_group"] is False
        assert "travel_time_up" in attrs
        assert "travel_time_down" in attrs
        assert "tilt_step_time_up" in attrs
        assert "tilt_step_time_down" in attrs
        assert "tilt_steps" in attrs


# ===========================================================================
# async_open_cover / async_close_cover
# ===========================================================================


class TestOpenClose:
    """Test open and close cover methods."""

    @pytest.mark.asyncio
    async def test_open_cover_sends_open_command(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_open_cover()

        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_open_cover_sets_known_position(self):
        cover = _make_cover()
        cover._known_position = False

        await cover.async_open_cover()

        assert cover._known_position is True

    @pytest.mark.asyncio
    async def test_open_cover_starts_tracking(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_open_cover()

        assert cover._move_direction == "opening"
        assert cover._move_target_pos == 100

    @pytest.mark.asyncio
    async def test_close_cover_sends_close_command(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_close_cover()

        assert _last_button_pressed(cover) == "button.close"

    @pytest.mark.asyncio
    async def test_close_cover_starts_tracking(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_close_cover()

        assert cover._move_direction == "closing"
        assert cover._move_target_pos == 0


# ===========================================================================
# async_set_cover_position
# ===========================================================================


class TestSetCoverPosition:
    """Test set_cover_position method."""

    @pytest.mark.asyncio
    async def test_set_position_opens_when_target_above(self):
        cover = _make_cover()
        cover._current_cover_position = 20
        cover._known_position = True

        await cover.async_set_cover_position(position=80)

        assert _last_button_pressed(cover) == "button.open"
        assert cover._move_direction == "opening"
        assert cover._move_target_pos == 80

    @pytest.mark.asyncio
    async def test_set_position_closes_when_target_below(self):
        cover = _make_cover()
        cover._current_cover_position = 80
        cover._known_position = True

        await cover.async_set_cover_position(position=20)

        assert _last_button_pressed(cover) == "button.close"
        assert cover._move_direction == "closing"
        assert cover._move_target_pos == 20

    @pytest.mark.asyncio
    async def test_set_position_skips_when_already_at_target(self):
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True

        await cover.async_set_cover_position(position=50)

        cover.hass.services.async_call.assert_not_called()


# ===========================================================================
# async_stop_cover
# ===========================================================================


class TestStopCover:
    """Test stop cover method."""

    @pytest.mark.asyncio
    async def test_stop_cover_sends_stop_command(self):
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "opening"

        await cover.async_stop_cover()

        assert _last_button_pressed(cover) == "button.stop"

    @pytest.mark.asyncio
    async def test_stop_cover_infers_tilt_100_when_opening(self):
        cover = _make_cover()
        cover._move_direction = "opening"
        cover._current_tilt_position = 0

        await cover.async_stop_cover()

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_stop_cover_infers_tilt_0_when_closing(self):
        cover = _make_cover()
        cover._move_direction = "closing"
        cover._current_tilt_position = 100

        await cover.async_stop_cover()

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_stop_cover_clears_movement_tracking(self):
        cover = _make_cover()
        cover._move_direction = "opening"

        await cover.async_stop_cover()

        assert cover._move_direction is None


# ===========================================================================
# Tilt methods
# ===========================================================================


class TestTilt:
    """Test tilt cover methods."""

    @pytest.mark.asyncio
    async def test_open_tilt_increments_by_one_step(self):
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_open_cover_tilt()

        # step 3 -> step 4 = 67%
        assert cover._current_tilt_position == 67

    @pytest.mark.asyncio
    async def test_close_tilt_decrements_by_one_step(self):
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_close_cover_tilt()

        # step 3 -> step 2 = 33%
        assert cover._current_tilt_position == 33

    @pytest.mark.asyncio
    async def test_open_tilt_clamps_at_max(self):
        cover = _make_cover()
        cover._current_tilt_position = 100  # step 6
        cover._known_tilt_position = True

        await cover.async_open_cover_tilt()

        # already at max, stays at 100
        assert cover._current_tilt_position == 100

    @pytest.mark.asyncio
    async def test_close_tilt_clamps_at_min(self):
        cover = _make_cover()
        cover._current_tilt_position = 0  # step 0
        cover._known_tilt_position = True

        await cover.async_close_cover_tilt()

        # already at min, stays at 0
        assert cover._current_tilt_position == 0

    @pytest.mark.asyncio
    async def test_set_tilt_position_snaps_to_step(self):
        cover = _make_cover()
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover.async_set_cover_tilt_position(tilt_position=45)

        # 45% snaps to step 3 = 50%
        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_set_tilt_sends_correct_number_of_commands(self):
        cover = _make_cover()
        cover._current_tilt_position = 0  # step 0
        cover._known_tilt_position = True

        await cover.async_set_cover_tilt_position(tilt_position=50)

        # step 0 -> step 3 = 3 tilt_up commands
        assert cover.hass.services.async_call.call_count == 3
        for call in cover.hass.services.async_call.call_args_list:
            assert call[0][2]["entity_id"] == "button.tilt_up"

    @pytest.mark.asyncio
    async def test_stop_tilt_sends_stop_command(self):
        cover = _make_cover()

        await cover.async_stop_cover_tilt()

        assert _last_button_pressed(cover) == "button.stop"


# ===========================================================================
# async_send_named_command
# ===========================================================================


class TestSendNamedCommand:
    """Test send_named_command dispatches correctly."""

    @pytest.mark.asyncio
    async def test_send_named_open(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_send_named_command("open")

        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_send_named_close(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_send_named_command("close")

        assert _last_button_pressed(cover) == "button.close"

    @pytest.mark.asyncio
    async def test_send_named_stop(self):
        cover = _make_cover()

        await cover.async_send_named_command("stop")

        assert _last_button_pressed(cover) == "button.stop"

    @pytest.mark.asyncio
    async def test_send_named_tilt_up(self):
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True

        await cover.async_send_named_command("tilt_up")

        assert _last_button_pressed(cover) == "button.tilt_up"

    @pytest.mark.asyncio
    async def test_send_named_tilt_down(self):
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True

        await cover.async_send_named_command("tilt_down")

        assert _last_button_pressed(cover) == "button.tilt_down"


# ===========================================================================
# _start_cover_move: normal behaviour (regression)
# ===========================================================================


class TestStartCoverMove:
    """Test _start_cover_move normal and force behaviour."""

    @pytest.mark.asyncio
    async def test_skips_when_already_at_target(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(0)

        cover.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_command_when_not_at_target(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(100)

        cover.hass.services.async_call.assert_called_once()
        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_force_sends_close_when_already_closed(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(0, force=True)

        cover.hass.services.async_call.assert_called_once()
        assert _last_button_pressed(cover) == "button.close"

    @pytest.mark.asyncio
    async def test_force_sends_open_when_already_open(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover._start_cover_move(100, force=True)

        cover.hass.services.async_call.assert_called_once()
        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_force_uses_full_travel_time_for_close(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(0, force=True)

        assert cover._move_duration == DEFAULT_TRAVEL_TIME_DOWN
        assert cover._move_direction == "closing"

    @pytest.mark.asyncio
    async def test_force_uses_full_travel_time_for_open(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover._start_cover_move(100, force=True)

        assert cover._move_duration == DEFAULT_TRAVEL_TIME_UP
        assert cover._move_direction == "opening"

    @pytest.mark.asyncio
    async def test_partial_move_calculates_proportional_duration(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(50)

        # 50% of travel_time_up
        assert cover._move_duration == pytest.approx(DEFAULT_TRAVEL_TIME_UP * 0.5)


# ===========================================================================
# async_force_move
# ===========================================================================


class TestForceMove:
    """Test async_force_move service method."""

    @pytest.mark.asyncio
    async def test_force_close_sets_known_position(self):
        cover = _make_cover()
        cover._known_position = False

        await cover.async_force_move("close")

        assert cover._known_position is True
        assert _last_button_pressed(cover) == "button.close"

    @pytest.mark.asyncio
    async def test_force_open_sets_known_position(self):
        cover = _make_cover()
        cover._known_position = False

        await cover.async_force_move("open")

        assert cover._known_position is True
        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_force_close_when_already_closed(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_force_move("close")

        cover.hass.services.async_call.assert_called_once()
        assert cover._move_direction == "closing"

    @pytest.mark.asyncio
    async def test_force_open_when_already_open(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_force_move("open")

        cover.hass.services.async_call.assert_called_once()
        assert cover._move_direction == "opening"


# ===========================================================================
# WaremaEWFSNativeGroupCover
# ===========================================================================


class TestNativeGroupCover:
    """Test native group cover specifics."""

    @pytest.mark.asyncio
    async def test_start_cover_move_skips_when_at_target(self):
        cover = _make_native_group()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(0)

        cover.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_cover_move_force_sends_when_at_target(self):
        cover = _make_native_group()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(0, force=True)

        cover.hass.services.async_call.assert_called_once()
        assert _last_button_pressed(cover) == "button.close"

    @pytest.mark.asyncio
    async def test_force_move_close(self):
        cover = _make_native_group()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_force_move("close")

        cover.hass.services.async_call.assert_called_once()
        assert cover._move_direction == "closing"

    @pytest.mark.asyncio
    async def test_force_move_open(self):
        cover = _make_native_group()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_force_move("open")

        cover.hass.services.async_call.assert_called_once()
        assert cover._move_direction == "opening"

    @pytest.mark.asyncio
    async def test_uses_full_travel_time_for_any_target(self):
        """Native group always uses full travel time, not proportional."""
        cover = _make_native_group()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._start_cover_move(100)

        assert cover._move_duration == DEFAULT_TRAVEL_TIME_UP
        assert cover._move_target_pos == 100

    @pytest.mark.asyncio
    async def test_open_moves_target_to_100(self):
        cover = _make_native_group()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_open_cover()

        assert cover._move_target_pos == 100

    @pytest.mark.asyncio
    async def test_close_moves_target_to_0(self):
        cover = _make_native_group()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_close_cover()

        assert cover._move_target_pos == 0


# ===========================================================================
# async_force_move - tilt side-effect
# ===========================================================================


class TestForceMoveWithTilt:
    """Test that force_move immediately sets the tilt to the correct position."""

    @pytest.mark.asyncio
    async def test_force_close_sets_tilt_to_zero(self):
        cover = _make_cover()
        cover._current_tilt_position = 100
        cover._known_tilt_position = True

        await cover.async_force_move("close")

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_force_open_sets_tilt_to_100(self):
        cover = _make_cover()
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover.async_force_move("open")

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_force_close_sets_tilt_even_when_already_closed(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._current_tilt_position = 67
        cover._known_position = True

        await cover.async_force_move("close")

        assert cover._current_tilt_position == 0

    @pytest.mark.asyncio
    async def test_force_open_sets_tilt_even_when_already_open(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._current_tilt_position = 33
        cover._known_position = True

        await cover.async_force_move("open")

        assert cover._current_tilt_position == 100


# ===========================================================================
# async_simulate_command on WaremaEWFSCover
# ===========================================================================


class TestSimulateCommand:
    """Test simulate_command updates state without sending hardware commands."""

    @pytest.mark.asyncio
    async def test_simulate_open_starts_tracking_without_hardware(self):
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_simulate_command("open")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction == "opening"
        assert cover._move_target_pos == 100

    @pytest.mark.asyncio
    async def test_simulate_close_starts_tracking_without_hardware(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_simulate_command("close")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction == "closing"
        assert cover._move_target_pos == 0

    @pytest.mark.asyncio
    async def test_simulate_open_sets_known_position(self):
        cover = _make_cover()
        cover._known_position = False

        await cover.async_simulate_command("open")

        assert cover._known_position is True

    @pytest.mark.asyncio
    async def test_simulate_open_skips_when_already_at_target(self):
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_simulate_command("open")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_stop_clears_tracking_without_hardware(self):
        cover = _make_cover()
        cover._move_direction = "opening"

        await cover.async_simulate_command("stop")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_stop_sets_tilt_100_when_opening(self):
        cover = _make_cover()
        cover._move_direction = "opening"
        cover._current_tilt_position = 0

        await cover.async_simulate_command("stop")

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_stop_sets_tilt_0_when_closing(self):
        cover = _make_cover()
        cover._move_direction = "closing"
        cover._current_tilt_position = 100

        await cover.async_simulate_command("stop")

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_tilt_up_increments_by_one_step(self):
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_simulate_command("tilt_up")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 67  # step 4

    @pytest.mark.asyncio
    async def test_simulate_tilt_down_decrements_by_one_step(self):
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_simulate_command("tilt_down")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 33  # step 2

    @pytest.mark.asyncio
    async def test_simulate_tilt_up_clamps_at_max(self):
        cover = _make_cover()
        cover._current_tilt_position = 100  # step 6

        await cover.async_simulate_command("tilt_up")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 100

    @pytest.mark.asyncio
    async def test_simulate_tilt_down_clamps_at_min(self):
        cover = _make_cover()
        cover._current_tilt_position = 0  # step 0

        await cover.async_simulate_command("tilt_down")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 0

    # ------------------------------------------------------------------
    # Tilt update when simulated move starts (non-zero duration)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_close_tilt_updated_when_move_finishes(self):
        """After a simulated close completes, tilt must be set to 0."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._current_tilt_position = 67
        cover._known_position = True
        cover._known_tilt_position = True

        await cover.async_simulate_command("close")
        # Simulate the timer firing (cover finished moving)
        await cover._finish_cover_move()

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_open_tilt_updated_when_move_finishes(self):
        """After a simulated open completes, tilt must be set to 100."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._current_tilt_position = 33
        cover._known_position = True
        cover._known_tilt_position = True

        await cover.async_simulate_command("open")
        await cover._finish_cover_move()

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    # ------------------------------------------------------------------
    # Tilt update when cover is already at the target (duration == 0)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_close_sets_tilt_0_when_already_closed(self):
        """simulate_command('close') must set tilt to 0 even when position is already 0."""
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._current_tilt_position = 67
        cover._known_position = True
        cover._known_tilt_position = True

        await cover.async_simulate_command("close")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_open_sets_tilt_100_when_already_open(self):
        """simulate_command('open') must set tilt to 100 even when position is already 100."""
        cover = _make_cover()
        cover._current_cover_position = 100
        cover._current_tilt_position = 33
        cover._known_position = True
        cover._known_tilt_position = True

        await cover.async_simulate_command("open")

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True


class TestSimulateSetTiltPosition:
    """Test async_simulate_set_tilt_position sets tilt without hardware."""

    @pytest.mark.asyncio
    async def test_sets_exact_snapped_tilt_position(self):
        cover = _make_cover()
        cover._current_tilt_position = 0

        await cover.async_simulate_set_tilt_position(tilt_position=45)

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 50  # snapped to step 3

    @pytest.mark.asyncio
    async def test_sets_tilt_to_100(self):
        cover = _make_cover()
        cover._current_tilt_position = 0

        await cover.async_simulate_set_tilt_position(tilt_position=100)

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_sets_tilt_to_0(self):
        cover = _make_cover()
        cover._current_tilt_position = 100

        await cover.async_simulate_set_tilt_position(tilt_position=0)

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 0

    @pytest.mark.asyncio
    async def test_multi_step_jump_sets_target_directly(self):
        """Unlike simulate_command tilt_up (one step), this sets any target directly."""
        cover = _make_cover()
        cover._current_tilt_position = 0  # step 0

        await cover.async_simulate_set_tilt_position(tilt_position=100)

        cover.hass.services.async_call.assert_not_called()
        assert cover._current_tilt_position == 100  # jumped to step 6 directly


# ===========================================================================
# Native group - member propagation (fanout)
# ===========================================================================


class TestNativeGroupFanout:
    """Test that native group propagates state changes to member entities."""

    @pytest.mark.asyncio
    async def test_open_cover_fanouts_simulate_open_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_open_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "open"
        assert "cover.member_a" in sim_calls[0][0][2]["entity_id"]

    @pytest.mark.asyncio
    async def test_close_cover_fanouts_simulate_close_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_close_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "close"

    @pytest.mark.asyncio
    async def test_force_move_fanouts_simulate_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_cover_position = 0

        await cover.async_force_move("close")

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "close"

    @pytest.mark.asyncio
    async def test_open_cover_tilt_fanouts_tilt_position_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_open_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        tilt_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_SET_TILT]
        assert len(tilt_calls) == 1
        assert tilt_calls[0][0][2]["tilt_position"] == 67  # step 3 → step 4

    @pytest.mark.asyncio
    async def test_close_cover_tilt_fanouts_tilt_position_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True

        await cover.async_close_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        tilt_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_SET_TILT]
        assert len(tilt_calls) == 1
        assert tilt_calls[0][0][2]["tilt_position"] == 33  # step 3 → step 2

    @pytest.mark.asyncio
    async def test_set_cover_tilt_position_fanouts_snapped_value_to_members(self):
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover.async_set_cover_tilt_position(tilt_position=45)

        calls = cover.hass.services.async_call.call_args_list
        tilt_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_SET_TILT]
        assert len(tilt_calls) == 1
        # 45% snaps to step 3 = 50%
        assert tilt_calls[0][0][2]["tilt_position"] == 50

    @pytest.mark.asyncio
    async def test_tilt_fanout_sends_no_hardware_to_member_buttons(self):
        """Verify tilt fanout never triggers button.press on member buttons."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover.async_set_cover_tilt_position(tilt_position=100)

        calls = cover.hass.services.async_call.call_args_list
        button_calls = [c for c in calls if c[0][0] == "button"]
        # Only the group's own tilt_up hardware button should be pressed, not member buttons
        for call in button_calls:
            assert call[0][2]["entity_id"] == "button.tilt_up"

    @pytest.mark.asyncio
    async def test_fanout_uses_correct_member_entity_ids(self):
        members = ["cover.bedroom", "cover.kitchen"]
        cover = _make_native_group_with_members(members=members)
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_open_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs"]
        assert sim_calls[0][0][2]["entity_id"] == members


# ===========================================================================
# Native group - stop command propagation (bug-fix coverage)
# ===========================================================================


class TestNativeGroupStopFanout:
    """Test that stop commands on native groups fanout simulate('stop') to members."""

    @pytest.mark.asyncio
    async def test_stop_cover_fanouts_simulate_stop_to_members(self):
        """async_stop_cover must fanout simulate('stop') to all members."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"
        assert "cover.member_a" in sim_calls[0][0][2]["entity_id"]

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_fanouts_simulate_stop_to_members(self):
        """async_stop_cover_tilt must fanout simulate('stop') to all members."""
        cover = _make_native_group_with_members()

        await cover.async_stop_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_stop_cover_sends_hardware_stop_and_simulate_stop(self):
        """async_stop_cover sends both the hardware button.press and the member fanout."""
        cover = _make_native_group_with_members()
        cover._move_direction = "closing"

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        button_calls = [c for c in calls if c[0][0] == "button" and c[0][1] == "press"]
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(button_calls) == 1
        assert button_calls[0][0][2]["entity_id"] == "button.stop"
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_sends_hardware_stop_and_simulate_stop(self):
        """async_stop_cover_tilt sends both the hardware button.press and the member fanout."""
        cover = _make_native_group_with_members()

        await cover.async_stop_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        button_calls = [c for c in calls if c[0][0] == "button" and c[0][1] == "press"]
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(button_calls) == 1
        assert button_calls[0][0][2]["entity_id"] == "button.stop"
        assert len(sim_calls) == 1

    @pytest.mark.asyncio
    async def test_stop_cover_clears_group_move_direction(self):
        """async_stop_cover must clear the group's own _move_direction."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"

        await cover.async_stop_cover()

        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_stop_cover_targets_all_members(self):
        """All configured members must receive the simulate stop."""
        members = ["cover.blind_1", "cover.blind_2", "cover.blind_3"]
        cover = _make_native_group_with_members(members=members)
        cover._move_direction = "closing"

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2]["entity_id"] == members

    @pytest.mark.asyncio
    async def test_stop_cover_infers_tilt_100_while_opening(self):
        """Group tilt must be set to 100 when stopping while opening."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"
        cover._current_tilt_position = 0

        await cover.async_stop_cover()

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_stop_cover_infers_tilt_0_while_closing(self):
        """Group tilt must be set to 0 when stopping while closing."""
        cover = _make_native_group_with_members()
        cover._move_direction = "closing"
        cover._current_tilt_position = 100

        await cover.async_stop_cover()

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_stop_cover_does_not_fanout_when_no_members(self):
        """async_stop_cover with no valid members must still send hardware stop but no fanout."""
        cover = _make_native_group()
        cover._members = []
        cover._revalidate_group_members = MagicMock()
        cover._move_direction = "opening"

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs"]
        assert len(sim_calls) == 0
        button_calls = [c for c in calls if c[0][0] == "button"]
        assert len(button_calls) == 1


# ===========================================================================
# Native group - stop command: end-to-end member state verification
# ===========================================================================


def _make_hass_with_service_routing(
    member_entities: dict[str, WaremaEWFSCover],
) -> MagicMock:
    """Return a mock hass that routes warema_ewfs service calls to real member entities.

    This lets integration-level tests verify that member entities' internal state
    (move_direction, tilt_position, etc.) is properly updated after a native group
    forwards a simulate command.
    """
    hass = _make_hass()

    async def route_call(domain: str, service: str, data: dict, blocking: bool = False) -> None:
        entity_ids = data.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        for eid in entity_ids:
            member = member_entities.get(eid)
            if member is None:
                continue
            if domain == "warema_ewfs" and service == SERVICE_SIMULATE_COMMAND:
                await member.async_simulate_command(data[ATTR_COMMAND])
            elif domain == "warema_ewfs" and service == SERVICE_SIMULATE_SET_TILT:
                await member.async_simulate_set_tilt_position(data["tilt_position"])

    hass.services.async_call = AsyncMock(side_effect=route_call)
    return hass


def _make_member_cover(hass: MagicMock, entity_id: str) -> WaremaEWFSCover:
    """Create a WaremaEWFSCover wired to the shared hass mock."""
    member = WaremaEWFSCover(hass, _make_config())
    member.async_write_ha_state = MagicMock()
    member.entity_id = entity_id
    return member


class TestNativeGroupStopBlindspots:
    """Tests that expose edge-cases and previously untested behaviour in native group stop handling."""

    # ------------------------------------------------------------------
    # BUG: async_stop_cover_tilt does NOT clear group's cover-move tracking
    # _stop_tilt_tracking() -> _cleanup_interval_listener() returns early
    # when _move_direction is set, leaving the group stuck as "opening/closing"
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_clears_group_move_direction_during_cover_move(self):
        """async_stop_cover_tilt must also stop the group's own cover-move tracking."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"
        cover._move_started_at = 0.0
        cover._move_duration = 30.0

        await cover.async_stop_cover_tilt()

        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_group_is_not_opening_in_ui_after_stop_cover_tilt(self):
        """is_opening must be False on the group itself after async_stop_cover_tilt."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"

        await cover.async_stop_cover_tilt()

        assert cover.is_opening is False
        assert cover.is_closing is False

    @pytest.mark.asyncio
    async def test_group_is_not_closing_in_ui_after_stop_cover_tilt(self):
        """is_closing must be False on the group itself after async_stop_cover_tilt."""
        cover = _make_native_group_with_members()
        cover._move_direction = "closing"

        await cover.async_stop_cover_tilt()

        assert cover.is_closing is False
        assert cover.is_opening is False

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_infers_tilt_100_while_opening(self):
        """When stopping via stop_cover_tilt while opening, group tilt must be set to 100."""
        cover = _make_native_group_with_members()
        cover._move_direction = "opening"
        cover._current_tilt_position = 0

        await cover.async_stop_cover_tilt()

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_infers_tilt_0_while_closing(self):
        """When stopping via stop_cover_tilt while closing, group tilt must be set to 0."""
        cover = _make_native_group_with_members()
        cover._move_direction = "closing"
        cover._current_tilt_position = 100

        await cover.async_stop_cover_tilt()

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    # ------------------------------------------------------------------
    # Stop when already idle (move_direction is None)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stop_cover_when_idle_still_sends_hardware_stop(self):
        """A stop command when not moving must still press the hardware stop button."""
        cover = _make_native_group_with_members()
        cover._move_direction = None

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        button_calls = [c for c in calls if c[0][0] == "button"]
        assert len(button_calls) == 1
        assert button_calls[0][0][2]["entity_id"] == "button.stop"

    @pytest.mark.asyncio
    async def test_stop_cover_when_idle_still_fanouts_simulate_stop(self):
        """A stop command when not moving must still fanout simulate('stop') to members."""
        cover = _make_native_group_with_members()
        cover._move_direction = None

        await cover.async_stop_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    # ------------------------------------------------------------------
    # async_set_cover_position boundary at 50 %
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_cover_position_exactly_50_routes_to_open(self):
        """Position 50 % is the open boundary - must route to open."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_set_cover_position(position=50)

        button_calls = [c for c in cover.hass.services.async_call.call_args_list if c[0][0] == "button"]
        assert len(button_calls) == 1
        assert button_calls[0][0][2]["entity_id"] == "button.open"

    @pytest.mark.asyncio
    async def test_set_cover_position_49_routes_to_close(self):
        """Position 49 % is below the boundary - must route to close."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_set_cover_position(position=49)

        button_calls = [c for c in cover.hass.services.async_call.call_args_list if c[0][0] == "button"]
        assert len(button_calls) == 1
        assert button_calls[0][0][2]["entity_id"] == "button.close"

    @pytest.mark.asyncio
    async def test_set_cover_position_0_routes_to_close_with_fanout(self):
        cover = _make_native_group_with_members()
        cover._current_cover_position = 100
        cover._known_position = True

        await cover.async_set_cover_position(position=0)

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "close"

    @pytest.mark.asyncio
    async def test_set_cover_position_100_routes_to_open_with_fanout(self):
        cover = _make_native_group_with_members()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover.async_set_cover_position(position=100)

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "open"

    # ------------------------------------------------------------------
    # _refresh_group_timing picks max travel times from members
    # ------------------------------------------------------------------

    def test_refresh_group_timing_uses_max_travel_time_up(self):
        """_refresh_group_timing must use the slowest (max) travel_time_up across members."""
        cover = _make_native_group_with_members(members=["cover.a", "cover.b"])
        cover._revalidate_group_members = MagicMock()

        state_a = MagicMock()
        state_a.attributes = {
            "travel_time_up": 15.0,
            "travel_time_down": 18.0,
            "tilt_step_time_up": 0.3,
            "tilt_step_time_down": 0.4,
        }
        state_b = MagicMock()
        state_b.attributes = {
            "travel_time_up": 20.0,
            "travel_time_down": 12.0,
            "tilt_step_time_up": 0.5,
            "tilt_step_time_down": 0.2,
        }
        cover.hass.states.get = lambda eid: state_a if eid == "cover.a" else state_b

        cover._refresh_group_timing()

        assert cover._travel_time_up == pytest.approx(20.0)  # max(15, 20)
        assert cover._travel_time_down == pytest.approx(18.0)  # max(18, 12)
        assert cover._tilt_step_time_up == pytest.approx(0.5)  # max(0.3, 0.5)
        assert cover._tilt_step_time_down == pytest.approx(0.4)  # max(0.4, 0.2)

    def test_refresh_group_timing_single_member_updates_all_times(self):
        """With one member, all timing fields are updated from that member's state."""
        cover = _make_native_group_with_members(members=["cover.only"])
        cover._revalidate_group_members = MagicMock()

        state = MagicMock()
        state.attributes = {
            "travel_time_up": 25.0,
            "travel_time_down": 30.0,
            "tilt_step_time_up": 0.6,
            "tilt_step_time_down": 0.7,
        }
        cover.hass.states.get = MagicMock(return_value=state)

        cover._refresh_group_timing()

        assert cover._travel_time_up == pytest.approx(25.0)
        assert cover._travel_time_down == pytest.approx(30.0)
        assert cover._tilt_step_time_up == pytest.approx(0.6)
        assert cover._tilt_step_time_down == pytest.approx(0.7)

    def test_refresh_group_timing_ignores_member_with_no_state(self):
        """Members without state (not yet loaded) must not reset timing to defaults."""
        cover = _make_native_group_with_members(members=["cover.a", "cover.missing"])
        cover._revalidate_group_members = MagicMock()
        cover._travel_time_up = 10.0  # pre-set to a known value

        state_a = MagicMock()
        state_a.attributes = {
            "travel_time_up": 22.0,
            "travel_time_down": 24.0,
            "tilt_step_time_up": 0.4,
            "tilt_step_time_down": 0.3,
        }

        def get_state(eid):
            return state_a if eid == "cover.a" else None

        cover.hass.states.get = get_state

        cover._refresh_group_timing()

        # Only cover.a contributes; cover.missing is silently skipped
        assert cover._travel_time_up == pytest.approx(22.0)

    # ------------------------------------------------------------------
    # Member already finished its tracking when group stop arrives
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stop_fanout_to_already_idle_member_leaves_tilt_unchanged(self):
        """simulate('stop') on a member that is already idle must not alter its tilt."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = None  # already finished tracking
        member._current_tilt_position = 100
        member._known_tilt_position = True

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "opening"

        await group.async_stop_cover()

        # Member was idle - tilt must stay as-is
        assert member._current_tilt_position == 100
        assert member._move_direction is None

    # ------------------------------------------------------------------
    # async_stop_cover_tilt also clears member cover tracking (end-to-end)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_clears_member_cover_tracking(self):
        """async_stop_cover_tilt must fanout simulate('stop') and clear member cover tracking."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "opening"
        member._current_tilt_position = 50

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "opening"

        await group.async_stop_cover_tilt()

        assert member._move_direction is None

    @pytest.mark.asyncio
    async def test_stop_cover_tilt_sets_member_tilt_to_100_while_opening(self):
        """Member tilt must become 100 when group stop_cover_tilt is called during opening."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "opening"
        member._current_tilt_position = 0

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "opening"

        await group.async_stop_cover_tilt()

        assert member._current_tilt_position == 100


class TestNativeGroupStopMemberState:
    """End-to-end tests: native group stop propagates correctly to member entity state."""

    @pytest.mark.asyncio
    async def test_member_move_direction_cleared_after_group_stop(self):
        """After async_stop_cover on the group, member _move_direction must be None."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "opening"
        member._move_started_at = 0.0
        member._move_duration = 30.0

        hass = _make_hass_with_service_routing({member_id: member})
        # Patch member hass so it shares the routing hass (for button presses the group sends)
        group = _make_native_group_with_members(hass=hass, members=[member_id])

        await group.async_stop_cover()

        assert member._move_direction is None

    @pytest.mark.asyncio
    async def test_member_tilt_set_to_100_when_opening_after_group_stop(self):
        """Member tilt must be set to 100 when group stops while opening."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "opening"
        member._current_tilt_position = 33
        member._known_tilt_position = True

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "opening"

        await group.async_stop_cover()

        assert member._current_tilt_position == 100
        assert member._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_member_tilt_set_to_0_when_closing_after_group_stop(self):
        """Member tilt must be set to 0 when group stops while closing."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "closing"
        member._current_tilt_position = 67
        member._known_tilt_position = True

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "closing"

        await group.async_stop_cover()

        assert member._current_tilt_position == 0
        assert member._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_all_members_move_direction_cleared_after_group_stop(self):
        """Every member in the group must have _move_direction cleared after group stop."""
        member_ids = ["cover.blind_1", "cover.blind_2"]
        shared_hass = _make_hass()
        members = {eid: _make_member_cover(shared_hass, eid) for eid in member_ids}
        for m in members.values():
            m._move_direction = "closing"

        hass = _make_hass_with_service_routing(members)
        group = _make_native_group_with_members(hass=hass, members=member_ids)
        group._move_direction = "closing"

        await group.async_stop_cover()

        for eid, member in members.items():
            assert member._move_direction is None, f"{eid} still has move_direction set"

    @pytest.mark.asyncio
    async def test_member_move_direction_cleared_after_group_stop_cover_tilt(self):
        """async_stop_cover_tilt must also clear the member's move direction."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "closing"
        member._move_started_at = 0.0
        member._move_duration = 22.0

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])

        await group.async_stop_cover_tilt()

        assert member._move_direction is None

    @pytest.mark.asyncio
    async def test_member_is_not_opening_in_ui_after_group_stop(self):
        """is_opening must return False on member entity after a group stop."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "opening"

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "opening"

        await group.async_stop_cover()

        assert member.is_opening is False
        assert member.is_closing is False

    @pytest.mark.asyncio
    async def test_member_is_not_closing_in_ui_after_group_stop(self):
        """is_closing must return False on member entity after a group stop."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._move_direction = "closing"

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._move_direction = "closing"

        await group.async_stop_cover()

        assert member.is_closing is False
        assert member.is_opening is False

    @pytest.mark.asyncio
    async def test_open_then_stop_leaves_member_idle(self):
        """Simulating an open command on a member and then stopping via the group leaves the member idle."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._current_cover_position = 0
        member._known_position = True

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._current_cover_position = 0
        group._known_position = True

        # Step 1: open via group → member should start tracking
        await group.async_open_cover()
        assert member._move_direction == "opening"

        # Step 2: stop via group → member must stop tracking
        group._move_direction = "opening"
        await group.async_stop_cover()
        assert member._move_direction is None


# ===========================================================================
# Reverse-direction while moving: first press acts as stop
# ===========================================================================


class TestReverseDirectionStop:
    """Test that commanding the opposite direction while moving acts as a stop."""

    # ------------------------------------------------------------------
    # Single shutter - hardware move
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_open_while_closing_sends_open_command_and_stops(self):
        """Sending open while closing must send the open button but stop tracking."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "closing"
        cover._move_started_at = 0.0
        cover._move_duration = 20.0

        await cover._start_cover_move(100)

        assert _last_button_pressed(cover) == "button.open"
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_close_while_opening_sends_close_command_and_stops(self):
        """Sending close while opening must send the close button but stop tracking."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None  # prevent _refresh_estimates from overriding position
        cover._move_duration = 0.0

        await cover._start_cover_move(0)

        assert _last_button_pressed(cover) == "button.close"
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_open_while_closing_infers_tilt_0(self):
        """Stopping while closing means slats ended vertical (tilt=0)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "closing"
        cover._current_tilt_position = 67

        await cover._start_cover_move(100)

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_close_while_opening_infers_tilt_100(self):
        """Stopping while opening means slats ended horizontal (tilt=100)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "opening"
        cover._current_tilt_position = 33

        await cover._start_cover_move(0)

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_reverse_does_not_start_new_tracking(self):
        """After a reverse-direction stop, no new move timer must be scheduled."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "closing"
        cover._move_started_at = 0.0
        cover._move_duration = 20.0

        import custom_components.warema_ewfs.cover as cover_module

        timer_calls: list = []

        def fake_call_later(hass, delay, action):
            timer_calls.append(delay)
            return MagicMock()

        original = cover_module.async_call_later
        cover_module.async_call_later = fake_call_later
        try:
            await cover._start_cover_move(100)
        finally:
            cover_module.async_call_later = original

        assert len(timer_calls) == 0, "No new timer must be scheduled on a reverse-direction stop"

    @pytest.mark.asyncio
    async def test_same_direction_while_moving_is_not_treated_as_stop(self):
        """Sending open while already opening must not be treated as a stop."""
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True
        cover._move_direction = "opening"
        cover._move_started_at = 0.0
        cover._move_duration = 20.0

        # Opening while already opening: duration > 0 still, so nothing should change
        # Refresh sets current position based on elapsed; let's start from scratch
        cover._move_direction = None
        await cover._start_cover_move(100)

        assert cover._move_direction == "opening"

    @pytest.mark.asyncio
    async def test_reverse_direction_via_async_open_cover(self):
        """async_open_cover while closing must stop (not start opening)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "closing"

        await cover.async_open_cover()

        assert cover._move_direction is None
        assert _last_button_pressed(cover) == "button.open"

    @pytest.mark.asyncio
    async def test_reverse_direction_via_async_close_cover(self):
        """async_close_cover while opening must stop (not start closing)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "opening"

        await cover.async_close_cover()

        assert cover._move_direction is None
        assert _last_button_pressed(cover) == "button.close"

    # ------------------------------------------------------------------
    # Single shutter - simulated move (members receiving simulate commands)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_open_while_closing_stops_without_hardware(self):
        """_simulate_cover_move open while closing must stop tracking; no button pressed."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "closing"

        await cover._simulate_cover_move(100)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_close_while_opening_stops_without_hardware(self):
        """_simulate_cover_move close while opening must stop tracking; no button pressed."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "opening"

        await cover._simulate_cover_move(0)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_open_while_closing_infers_tilt_0(self):
        """Simulated reverse while closing sets tilt=0 (slats were vertical when stopped)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "closing"
        cover._current_tilt_position = 67

        await cover._simulate_cover_move(100)

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_close_while_opening_infers_tilt_100(self):
        """Simulated reverse while opening sets tilt=100 (slats were horizontal when stopped)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._move_direction = "opening"
        cover._current_tilt_position = 33

        await cover._simulate_cover_move(0)

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_simulate_open_while_closing_via_simulate_command(self):
        """simulate_command('open') while closing must stop (no tracking of open)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "closing"

        await cover.async_simulate_command("open")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_close_while_opening_via_simulate_command(self):
        """simulate_command('close') while opening must stop (no tracking of close)."""
        cover = _make_cover()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "opening"

        await cover.async_simulate_command("close")

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    # ------------------------------------------------------------------
    # Native group - fanout propagation on reverse direction
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_native_group_open_while_closing_fanouts_simulate_stop(self):
        """Native group: open while closing must fanout simulate('stop') not simulate('open')."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "closing"

        await cover.async_open_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_native_group_close_while_opening_fanouts_simulate_stop(self):
        """Native group: close while opening must fanout simulate('stop') not simulate('close')."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 50
        cover._known_position = True
        cover._move_direction = "opening"

        await cover.async_close_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_native_group_open_while_idle_fanouts_simulate_open(self):
        """Native group: open while idle must still fanout simulate('open')."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 0
        cover._known_position = True
        cover._move_direction = None

        await cover.async_open_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "open"

    @pytest.mark.asyncio
    async def test_native_group_close_while_idle_fanouts_simulate_close(self):
        """Native group: close while idle must still fanout simulate('close')."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 100
        cover._known_position = True
        cover._move_direction = None

        await cover.async_close_cover()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "close"

    @pytest.mark.asyncio
    async def test_native_group_open_while_closing_group_direction_cleared(self):
        """Native group itself must also have _move_direction cleared on reverse."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 50
        cover._move_direction = "closing"

        await cover.async_open_cover()

        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_native_group_close_while_opening_group_direction_cleared(self):
        """Native group itself must also have _move_direction cleared on reverse."""
        cover = _make_native_group_with_members()
        cover._current_cover_position = 50
        cover._move_direction = "opening"

        await cover.async_close_cover()

        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_native_group_reverse_propagates_stop_to_member_state(self):
        """End-to-end: opening while group is closing stops member tracking too."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._current_cover_position = 50
        member._move_direction = "closing"

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._current_cover_position = 50
        group._move_direction = "closing"

        await group.async_open_cover()

        assert member._move_direction is None

    @pytest.mark.asyncio
    async def test_native_group_reverse_member_tilt_reflects_stop_direction(self):
        """Member tilt must be 0 when group reverses from closing (stopped while closing)."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._current_cover_position = 50
        member._move_direction = "closing"
        member._current_tilt_position = 67

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._current_cover_position = 50
        group._move_direction = "closing"

        await group.async_open_cover()

        # Member was closing when stopped → tilt = 0
        assert member._current_tilt_position == 0


# ===========================================================================
# Tilt in opposite direction while cover is moving also stops the motor
# ===========================================================================


class TestOppositeTiltStopsMove:
    """Test that a tilt command in the opposite direction to an ongoing cover move stops it."""

    # ------------------------------------------------------------------
    # Single shutter - _start_tilt_move
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_tilt_down_while_opening_stops_and_sends_tilt_down(self):
        """tilt_down while opening must send the tilt_down button and stop tracking."""
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None
        cover._move_duration = 0.0

        await cover._start_tilt_move(0)  # tilt_down direction

        assert _last_button_pressed(cover) == "button.tilt_down"
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_tilt_up_while_closing_stops_and_sends_tilt_up(self):
        """tilt_up while closing must send the tilt_up button and stop tracking."""
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None
        cover._move_duration = 0.0

        await cover._start_tilt_move(100)  # tilt_up direction

        assert _last_button_pressed(cover) == "button.tilt_up"
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_tilt_down_while_opening_infers_tilt_100(self):
        """Stopped while opening → slats end horizontal (tilt=100)."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._start_tilt_move(0)

        assert cover._current_tilt_position == 100
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_tilt_up_while_closing_infers_tilt_0(self):
        """Stopped while closing → slats end vertical (tilt=0)."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._start_tilt_move(100)

        assert cover._current_tilt_position == 0
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_tilt_down_while_opening_via_async_close_cover_tilt(self):
        """async_close_cover_tilt while opening must stop cover tracking."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover.async_close_cover_tilt()

        assert cover._move_direction is None
        assert _last_button_pressed(cover) == "button.tilt_down"

    @pytest.mark.asyncio
    async def test_tilt_up_while_closing_via_async_open_cover_tilt(self):
        """async_open_cover_tilt while closing must stop cover tracking."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover.async_open_cover_tilt()

        assert cover._move_direction is None
        assert _last_button_pressed(cover) == "button.tilt_up"

    @pytest.mark.asyncio
    async def test_tilt_same_direction_does_not_stop_cover(self):
        """tilt_up while opening is same direction - cover tracking must NOT be stopped."""
        cover = _make_cover()
        cover._current_tilt_position = 0  # step 0, can go tilt_up
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._start_tilt_move(100)  # tilt_up - same direction as opening

        # Cover tracking is still running
        assert cover._move_direction == "opening"

    @pytest.mark.asyncio
    async def test_tilt_same_direction_closing_does_not_stop_cover(self):
        """tilt_down while closing is same direction - cover tracking must NOT be stopped."""
        cover = _make_cover()
        cover._current_tilt_position = 100  # step 6, can go tilt_down
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._start_tilt_move(0)  # tilt_down - same direction as closing

        assert cover._move_direction == "closing"

    @pytest.mark.asyncio
    async def test_tilt_up_while_opening_sends_no_command(self):
        """tilt_up while opening must send no button press at all."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._start_tilt_move(100)

        cover.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_tilt_down_while_closing_sends_no_command(self):
        """tilt_down while closing must send no button press at all."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._start_tilt_move(0)

        cover.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_tilt_up_while_opening_does_not_change_tilt_position(self):
        """tilt_up while opening must leave the tilt position unchanged."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._start_tilt_move(100)

        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_tilt_down_while_closing_does_not_change_tilt_position(self):
        """tilt_down while closing must leave the tilt position unchanged."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._start_tilt_move(0)

        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_tilt_down_while_idle_executes_normally(self):
        """tilt_down when cover is idle must execute the tilt step as normal."""
        cover = _make_cover()
        cover._current_tilt_position = 50  # step 3
        cover._known_tilt_position = True
        cover._move_direction = None

        # One step down: step 3 → step 2 = 33 %
        await cover._start_tilt_move(33)

        assert _last_button_pressed(cover) == "button.tilt_down"
        assert cover._current_tilt_position == 33  # step 2

    # ------------------------------------------------------------------
    # _simulate_tilt_move: same-direction no-op
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_tilt_up_while_opening_is_noop(self):
        """Simulated tilt_up while opening must be a no-op."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._simulate_tilt_move(100)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction == "opening"
        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_simulate_tilt_down_while_closing_is_noop(self):
        """Simulated tilt_down while closing must be a no-op."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._simulate_tilt_move(0)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction == "closing"
        assert cover._current_tilt_position == 50

    # ------------------------------------------------------------------
    # Native group: same-direction tilt produces no fanout
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_native_group_open_tilt_while_opening_produces_no_fanout(self):
        """open_cover_tilt while opening is a hardware no-op - nothing must be fanned out."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover.async_open_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        warema_calls = [c for c in calls if c[0][0] == "warema_ewfs"]
        assert len(warema_calls) == 0

    @pytest.mark.asyncio
    async def test_native_group_close_tilt_while_closing_produces_no_fanout(self):
        """close_cover_tilt while closing is a hardware no-op - nothing must be fanned out."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover.async_close_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        warema_calls = [c for c in calls if c[0][0] == "warema_ewfs"]
        assert len(warema_calls) == 0

    @pytest.mark.asyncio
    async def test_native_group_set_tilt_same_direction_produces_no_fanout(self):
        """set_cover_tilt_position in same direction while moving must produce no fanout."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 33  # step 2 - will move tilt_up to reach 100
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        from homeassistant.components.cover import ATTR_TILT_POSITION

        await cover.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 100})

        calls = cover.hass.services.async_call.call_args_list
        warema_calls = [c for c in calls if c[0][0] == "warema_ewfs"]
        assert len(warema_calls) == 0

    @pytest.mark.asyncio
    async def test_native_group_open_tilt_while_opening_cover_direction_unchanged(self):
        """After same-direction no-op, group cover tracking must still be active."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover.async_open_cover_tilt()

        assert cover._move_direction == "opening"

    # ===========================================================================
    # WaremaEWFSGroupCover - command_delay
    # ===========================================================================

    # ------------------------------------------------------------------
    # Single shutter - _simulate_tilt_move
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_tilt_down_while_opening_stops_without_hardware(self):
        """Simulated tilt_down while opening must stop tracking without sending hardware."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._simulate_tilt_move(0)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_tilt_up_while_closing_stops_without_hardware(self):
        """Simulated tilt_up while closing must stop tracking without sending hardware."""
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._simulate_tilt_move(100)

        cover.hass.services.async_call.assert_not_called()
        assert cover._move_direction is None

    @pytest.mark.asyncio
    async def test_simulate_tilt_down_while_opening_infers_tilt_100(self):
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover._simulate_tilt_move(0)

        assert cover._current_tilt_position == 100

    @pytest.mark.asyncio
    async def test_simulate_tilt_up_while_closing_infers_tilt_0(self):
        cover = _make_cover()
        cover._current_tilt_position = 50
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover._simulate_tilt_move(100)

        assert cover._current_tilt_position == 0

    # ------------------------------------------------------------------
    # Native group - fanout propagation on opposite-tilt stop
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_native_group_close_tilt_while_opening_fanouts_simulate_stop(self):
        """close_cover_tilt while opening → fanout simulate('stop') not tilt position."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        await cover.async_close_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_native_group_open_tilt_while_closing_fanouts_simulate_stop(self):
        """open_cover_tilt while closing → fanout simulate('stop') not tilt position."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = "closing"
        cover._move_started_at = None

        await cover.async_open_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_native_group_set_tilt_opposite_while_opening_fanouts_simulate_stop(self):
        """set_cover_tilt_position in opposite direction while opening → fanout stop."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 67  # step 4 - will move tilt_down to reach 0
        cover._known_tilt_position = True
        cover._move_direction = "opening"
        cover._move_started_at = None

        from homeassistant.components.cover import ATTR_TILT_POSITION

        await cover.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 0})

        calls = cover.hass.services.async_call.call_args_list
        sim_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_COMMAND]
        assert len(sim_calls) == 1
        assert sim_calls[0][0][2][ATTR_COMMAND] == "stop"

    @pytest.mark.asyncio
    async def test_native_group_open_tilt_while_idle_fanouts_tilt_position(self):
        """open_cover_tilt while idle must fanout tilt position, not stop."""
        cover = _make_native_group_with_members()
        cover._current_tilt_position = 50
        cover._known_tilt_position = True
        cover._move_direction = None

        await cover.async_open_cover_tilt()

        calls = cover.hass.services.async_call.call_args_list
        tilt_calls = [c for c in calls if c[0][0] == "warema_ewfs" and c[0][1] == SERVICE_SIMULATE_SET_TILT]
        assert len(tilt_calls) == 1

    @pytest.mark.asyncio
    async def test_native_group_opposite_tilt_propagates_stop_to_member_state(self):
        """End-to-end: close_cover_tilt while opening clears member cover tracking."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._current_tilt_position = 50
        member._move_direction = "opening"
        member._move_started_at = None

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._current_tilt_position = 50
        group._move_direction = "opening"
        group._move_started_at = None

        await group.async_close_cover_tilt()

        assert member._move_direction is None

    @pytest.mark.asyncio
    async def test_native_group_opposite_tilt_member_tilt_inferred_from_stop_direction(self):
        """Member tilt must be 100 when stopped while opening (via opposite tilt)."""
        member_id = "cover.member_a"
        member = _make_member_cover(_make_hass(), member_id)
        member._current_tilt_position = 50
        member._move_direction = "opening"
        member._move_started_at = None

        hass = _make_hass_with_service_routing({member_id: member})
        group = _make_native_group_with_members(hass=hass, members=[member_id])
        group._current_tilt_position = 50
        group._move_direction = "opening"
        group._move_started_at = None

        await group.async_close_cover_tilt()

        assert member._current_tilt_position == 100


# ===========================================================================
# WaremaEWFSGroupCover - command_delay
# ===========================================================================


class TestGroupCommandDelay:
    """Test fan-out group command_delay behaviour."""

    @pytest.mark.asyncio
    async def test_without_delay_sends_single_batch_call(self):
        cover = _make_group_with_members(command_delay=0.0)

        await cover.async_open_cover()

        calls = [c for c in cover.hass.services.async_call.call_args_list if c[0][1] == "open_cover"]
        assert len(calls) == 1
        assert calls[0][0][2]["entity_id"] == ["cover.member_a", "cover.member_b"]

    @pytest.mark.asyncio
    async def test_with_delay_sends_one_call_per_member(self):
        cover = _make_group_with_members(command_delay=0.01)

        with pytest.MonkeyPatch().context() as mp:
            sleep_calls: list[float] = []

            async def fake_sleep(delay: float) -> None:
                sleep_calls.append(delay)

            mp.setattr(asyncio, "sleep", fake_sleep)
            await cover.async_open_cover()

        calls = [c for c in cover.hass.services.async_call.call_args_list if c[0][1] == "open_cover"]
        assert len(calls) == 2
        assert calls[0][0][2]["entity_id"] == "cover.member_a"
        assert calls[1][0][2]["entity_id"] == "cover.member_b"

    @pytest.mark.asyncio
    async def test_with_delay_sleeps_between_members_not_before_first(self):
        cover = _make_group_with_members(
            members=["cover.a", "cover.b", "cover.c"],
            command_delay=0.5,
        )

        with pytest.MonkeyPatch().context() as mp:
            sleep_calls: list[float] = []

            async def fake_sleep(delay: float) -> None:
                sleep_calls.append(delay)

            mp.setattr(asyncio, "sleep", fake_sleep)
            await cover.async_open_cover()

        # 3 members → 2 sleeps (not before the first command)
        assert len(sleep_calls) == 2
        assert all(s == pytest.approx(0.5) for s in sleep_calls)

    @pytest.mark.asyncio
    async def test_with_delay_single_member_no_sleep(self):
        cover = _make_group_with_members(members=["cover.only"], command_delay=0.5)

        with pytest.MonkeyPatch().context() as mp:
            sleep_calls: list[float] = []

            async def fake_sleep(delay: float) -> None:
                sleep_calls.append(delay)

            mp.setattr(asyncio, "sleep", fake_sleep)
            await cover.async_open_cover()

        assert len(sleep_calls) == 0

    @pytest.mark.asyncio
    async def test_default_command_delay_is_zero(self):
        cover = _make_group_with_members()
        assert cover._command_delay == DEFAULT_COMMAND_DELAY == 0.0


# ===========================================================================
# State restore after HA restart
# ===========================================================================


def _make_mock_state(position: int | None = None, tilt: int | None = None) -> MagicMock:
    """Build a fake last_state with the HA cover state attribute names."""
    state = MagicMock()
    attrs: dict[str, Any] = {}
    if position is not None:
        attrs[ATTR_CURRENT_POSITION] = position
    if tilt is not None:
        attrs[ATTR_CURRENT_TILT_POSITION] = tilt
    state.attributes = attrs
    return state


class TestStateRestore:
    """Test that position and tilt are correctly restored after a HA restart."""

    @pytest.mark.asyncio
    async def test_restores_position_from_current_position_attribute(self):
        cover = _make_cover()
        cover.async_get_last_state = AsyncMock(return_value=_make_mock_state(position=75))

        await cover.async_added_to_hass()

        assert cover._current_cover_position == 75
        assert cover._known_position is True

    @pytest.mark.asyncio
    async def test_restores_tilt_from_current_tilt_position_attribute(self):
        cover = _make_cover()
        cover.async_get_last_state = AsyncMock(return_value=_make_mock_state(tilt=50))

        await cover.async_added_to_hass()

        assert cover._current_tilt_position == 50
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_restores_both_position_and_tilt(self):
        cover = _make_cover()
        cover.async_get_last_state = AsyncMock(return_value=_make_mock_state(position=33, tilt=67))

        await cover.async_added_to_hass()

        assert cover._current_cover_position == 33
        assert cover._known_position is True
        assert cover._current_tilt_position == 67
        assert cover._known_tilt_position is True

    @pytest.mark.asyncio
    async def test_known_position_false_when_no_last_state(self):
        cover = _make_cover()
        cover.async_get_last_state = AsyncMock(return_value=None)

        await cover.async_added_to_hass()

        assert cover._known_position is False
        assert cover._known_tilt_position is False

    @pytest.mark.asyncio
    async def test_position_not_old_attr_name(self):
        """Regression: restore must NOT look up the service-call key 'position'."""
        cover = _make_cover()
        # Simulate a state that only has the old wrong key "position" (not "current_position")
        bad_state = MagicMock()
        bad_state.attributes = {"position": 80, "tilt_position": 50}
        cover.async_get_last_state = AsyncMock(return_value=bad_state)

        await cover.async_added_to_hass()

        # Should NOT restore - the wrong key must not be picked up
        assert cover._known_position is False
        assert cover._known_tilt_position is False


# ===========================================================================
# simulate_stop_delay - automatic motor-neutralisation after simulated moves
# ===========================================================================


def _make_cover_with_simulate_stop(delay: float, **config_overrides: Any) -> WaremaEWFSCover:
    """Create a cover with simulate_stop_delay configured and timer infrastructure mocked."""
    cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: delay, **config_overrides})
    # Capture the scheduled callback so tests can fire it manually
    cover._scheduled_simulate_stop_callback: Any = None

    return cover


class TestSimulateStopDelay:
    """Test that a simulated move sends an automatic hardware stop after simulate_stop_delay."""

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def test_default_simulate_stop_delay_is_zero(self):
        """Feature is off by default."""
        cover = _make_cover()
        assert cover._simulate_stop_delay == DEFAULT_SIMULATE_STOP_DELAY == 0.0

    def test_simulate_stop_delay_stored_from_config(self):
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 3.5})
        assert cover._simulate_stop_delay == pytest.approx(3.5)

    def test_simulate_stop_delay_in_extra_state_attributes(self):
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 4.0})
        assert cover.extra_state_attributes["simulate_stop_delay"] == pytest.approx(4.0)

    # ------------------------------------------------------------------
    # No auto-stop when delay is 0 (disabled)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_no_simulate_stop_timer_when_delay_is_zero(self):
        """When simulate_stop_delay == 0, no timer is scheduled after _finish_cover_move."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 0.0})
        cover._current_cover_position = 100
        cover._known_position = True
        cover._move_is_simulated = True
        cover._move_start_pos = 100
        cover._move_target_pos = 0
        cover._move_direction = "closing"
        cover._move_started_at = 0.0
        cover._move_duration = 22.0

        await cover._finish_cover_move()

        assert cover._unsub_simulate_stop_timer is None

    # ------------------------------------------------------------------
    # Timer is scheduled AFTER _finish_cover_move (not at command time)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_simulate_stop_timer_scheduled_after_finish_cover_move(self):
        """Timer must be scheduled inside _finish_cover_move, not in _simulate_cover_move."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cover._current_cover_position = 100
        cover._known_position = True

        import custom_components.warema_ewfs.cover as cover_module

        captured: list[Any] = []

        def fake_call_later(hass, delay, action):
            captured.append((delay, action))
            return MagicMock()

        original = cover_module.async_call_later
        cover_module.async_call_later = fake_call_later
        try:
            # Step 1: simulate_command schedules only the move-stop timer (NOT the simulate-stop)
            await cover.async_simulate_command("close")
            timers_after_command = len(captured)  # should be 1 (move-stop only)

            # Step 2: fire _finish_cover_move - NOW the simulate-stop timer must be added
            await cover._finish_cover_move()
            timers_after_finish = len(captured)
        finally:
            cover_module.async_call_later = original

        assert timers_after_command == 1, "Only move-stop timer should be scheduled at command time"
        assert timers_after_finish == 2, "simulate-stop timer must be scheduled after _finish_cover_move"
        delays = [c[0] for c in captured]
        assert 2.0 in delays, "simulate_stop_delay (2.0 s) must be among the scheduled delays"

    @pytest.mark.asyncio
    async def test_simulate_stop_timer_not_scheduled_for_normal_move(self):
        """Normal (hardware) moves must never schedule the simulate-stop timer."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cover._current_cover_position = 0
        cover._known_position = True

        import custom_components.warema_ewfs.cover as cover_module

        captured: list[float] = []

        def fake_call_later(hass, delay, action):
            captured.append(delay)
            return MagicMock()

        original = cover_module.async_call_later
        cover_module.async_call_later = fake_call_later
        try:
            await cover.async_open_cover()  # normal move
            await cover._finish_cover_move()  # finish it
        finally:
            cover_module.async_call_later = original

        # Only the move-stop timer (travel_time_up) must appear - never the 2.0 s simulate-stop
        assert 2.0 not in captured

    @pytest.mark.asyncio
    async def test_simulate_stop_timer_scheduled_when_delay_positive(self):
        """After _finish_cover_move for a simulated move, the simulate-stop timer appears."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 3.0})
        cover._current_cover_position = 100
        cover._known_position = True

        import custom_components.warema_ewfs.cover as cover_module

        captured: list[float] = []

        def fake_call_later(hass, delay, action):
            captured.append(delay)
            return MagicMock()

        original = cover_module.async_call_later
        cover_module.async_call_later = fake_call_later
        try:
            await cover.async_simulate_command("close")
            await cover._finish_cover_move()
        finally:
            cover_module.async_call_later = original

        assert 3.0 in captured

    # ------------------------------------------------------------------
    # _auto_stop_simulated_move behaviour (fires AFTER tracking is done)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_auto_stop_sends_hardware_stop_command(self):
        """_auto_stop_simulated_move sends a real stop command to clear direction lock."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        # Cover is already at rest (tracking finished); only the timer is pending
        cover._move_direction = None

        await cover._auto_stop_simulated_move()

        assert cover.hass.services.async_call.call_count == 1
        assert _last_button_pressed(cover) == "button.stop"

    @pytest.mark.asyncio
    async def test_auto_stop_does_not_change_position_or_tilt(self):
        """_auto_stop_simulated_move must not alter position/tilt - tracking is already done."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cover._current_cover_position = 0
        cover._current_tilt_position = 0
        cover._known_position = True
        cover._known_tilt_position = True
        cover._move_direction = None  # tracking already finished

        await cover._auto_stop_simulated_move()

        assert cover._current_cover_position == 0
        assert cover._current_tilt_position == 0

    @pytest.mark.asyncio
    async def test_auto_stop_clears_timer_ref(self):
        """_auto_stop_simulated_move clears the timer reference."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cover._unsub_simulate_stop_timer = MagicMock()  # simulate pending timer
        cover._move_direction = None

        await cover._auto_stop_simulated_move()

        assert cover._unsub_simulate_stop_timer is None

    # ------------------------------------------------------------------
    # Timer cancellation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stop_cover_tracking_cancels_simulate_stop_timer(self):
        """Stopping tracking explicitly cancels any pending simulate-stop timer."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cancel_mock = MagicMock()
        cover._unsub_simulate_stop_timer = cancel_mock

        cover._stop_cover_tracking()

        cancel_mock.assert_called_once()
        assert cover._unsub_simulate_stop_timer is None

    @pytest.mark.asyncio
    async def test_simulate_stop_timer_cancelled_when_normal_move_starts(self):
        """A new normal move cancels any pending simulate-stop timer."""
        cover = _make_cover(**{CONF_SIMULATE_STOP_DELAY: 2.0})
        cover._current_cover_position = 0
        cover._known_position = True
        cancel_mock = MagicMock()
        cover._unsub_simulate_stop_timer = cancel_mock

        # Starting a real/normal move should cancel the old simulate-stop timer
        await cover._start_cover_move(100)

        cancel_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_simulate_stop_full_delay_used_no_cap(self):
        """simulate_stop_delay is used in full - there is no cap at move duration."""
        cover = _make_cover(
            **{
                CONF_SIMULATE_STOP_DELAY: 5.0,
                CONF_TRAVEL_TIME_DOWN: 3.0,  # move duration shorter than delay
            }
        )
        cover._current_cover_position = 100
        cover._known_position = True

        import custom_components.warema_ewfs.cover as cover_module

        captured: list[float] = []

        def fake_call_later(hass, delay, action):
            captured.append(delay)
            return MagicMock()

        original = cover_module.async_call_later
        cover_module.async_call_later = fake_call_later
        try:
            await cover.async_simulate_command("close")
            await cover._finish_cover_move()
        finally:
            cover_module.async_call_later = original

        # simulate_stop timer must use the full 5.0 s - no cap at 3.0 s
        assert 5.0 in captured
        assert 3.0 not in [d for d in captured if d == 5.0]  # 3.0 is only the move timer

    @pytest.mark.asyncio
    async def test_move_is_simulated_flag_set_by_simulate_cover_move(self):
        """_move_is_simulated must be True after _simulate_cover_move and False after normal move."""
        cover = _make_cover()
        cover._current_cover_position = 0
        cover._known_position = True

        await cover._simulate_cover_move(100)
        assert cover._move_is_simulated is True

        # Starting a real move must clear the flag
        await cover._start_cover_move(0)
        assert cover._move_is_simulated is False


# ===========================================================================
# Configurable tilt step count
# ===========================================================================


class TestTiltStepCount:
    """Test that tilt step count is configurable and affects all tilt operations."""

    def test_default_tilt_step_count_is_7(self):
        cover = _make_cover()
        assert cover._tilt_step_count == 7
        assert cover.extra_state_attributes["tilt_steps"] == 7

    def test_custom_tilt_step_count_is_stored(self):
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        assert cover._tilt_step_count == 5
        assert cover.extra_state_attributes["tilt_steps"] == 5

    def test_tilt_steps_attribute_reflects_custom_count(self):
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 3})
        assert cover.extra_state_attributes["tilt_steps"] == 3

    @pytest.mark.asyncio
    async def test_open_tilt_increments_one_step_with_5_steps(self):
        """With 5 steps the valid percents are 0, 25, 50, 75, 100."""
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover.async_open_cover_tilt()

        # One step up from 0 with 5 steps → step 1 → 25 %
        assert _last_button_pressed(cover) == "button.tilt_up"
        assert cover._current_tilt_position == 25

    @pytest.mark.asyncio
    async def test_close_tilt_decrements_one_step_with_5_steps(self):
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        cover._current_tilt_position = 100
        cover._known_tilt_position = True

        await cover.async_close_cover_tilt()

        # One step down from 100 with 5 steps → step 3 → 75 %
        assert _last_button_pressed(cover) == "button.tilt_down"
        assert cover._current_tilt_position == 75

    @pytest.mark.asyncio
    async def test_set_tilt_position_snaps_to_5_step_grid(self):
        """Setting 40 % with 5 steps should snap to 50 % (nearest of 0,25,50,75,100)."""
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        from homeassistant.components.cover import ATTR_TILT_POSITION

        await cover.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 40})

        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_set_tilt_position_snaps_to_3_step_grid(self):
        """With 3 steps the valid percents are 0, 50, 100.
        70 % is closer to 50 % (distance 20) than to 100 % (distance 30)."""
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 3})
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        from homeassistant.components.cover import ATTR_TILT_POSITION

        await cover.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 70})

        assert cover._current_tilt_position == 50

    @pytest.mark.asyncio
    async def test_open_tilt_does_not_exceed_max_step_with_5_steps(self):
        """Opening tilt from 100 % (max step) should send no command."""
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        cover._current_tilt_position = 100
        cover._known_tilt_position = True
        cover.hass.services.async_call.reset_mock()

        await cover.async_open_cover_tilt()

        cover.hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulate_tilt_move_uses_custom_step_count(self):
        """simulate_tilt_move should advance by one step of the configured count."""
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        cover._current_tilt_position = 0
        cover._known_tilt_position = True

        await cover._simulate_tilt_move(100)

        # With 5 steps one step up from 0 → 25 %
        assert cover._current_tilt_position == 25

    @pytest.mark.asyncio
    async def test_simulate_set_tilt_position_snaps_with_custom_count(self):
        cover = _make_cover(**{CONF_TILT_STEP_COUNT: 5})
        await cover.async_simulate_set_tilt_position(tilt_position=60)
        # Nearest 5-step value to 60 % is 50 %
        assert cover._current_tilt_position == 50
