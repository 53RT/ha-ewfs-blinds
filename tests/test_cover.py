"""Tests for WaremaEWFSCover entity logic."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

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
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_SEND_STOP_AFTER_MOVE,
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
