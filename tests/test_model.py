import pytest

from custom_components.warema_ewfs.model import (
    clamp_percent,
    compute_cover_duration,
    compute_tilt_duration,
    infer_tilt_after_cover_move,
    should_send_auto_stop,
    tilt_percent_to_step,
    snap_to_tilt_step,
    tilt_step_to_percent,
)


def test_clamp_percent():
    assert clamp_percent(-3) == 0
    assert clamp_percent(19.6) == 20
    assert clamp_percent(205) == 100


def test_compute_cover_duration_uses_up_time_when_opening():
    duration = compute_cover_duration(current=20, target=70, time_up=30.0, time_down=20.0)
    assert duration == 15.0


def test_compute_cover_duration_uses_down_time_when_closing():
    duration = compute_cover_duration(current=70, target=20, time_up=30.0, time_down=20.0)
    assert duration == 10.0


def test_snap_to_tilt_step_for_7_steps():
    assert snap_to_tilt_step(0) == 0
    assert snap_to_tilt_step(11) == 17
    assert snap_to_tilt_step(39) == 33
    assert snap_to_tilt_step(100) == 100


def test_compute_tilt_duration_for_three_steps_up():
    # 0 -> 50 is roughly three 7-step increments.
    duration = compute_tilt_duration(current_tilt=0, target_tilt=50, step_time_up=0.3, step_time_down=0.6)
    assert duration == pytest.approx(0.9)


def test_compute_tilt_duration_for_one_step_down():
    duration = compute_tilt_duration(current_tilt=67, target_tilt=50, step_time_up=0.3, step_time_down=0.6)
    assert duration == 0.6


def test_should_send_auto_stop_for_cover_move_when_enabled():
    assert should_send_auto_stop(send_stop_after_move=True, is_tilt_move=False)


def test_should_not_send_auto_stop_for_cover_move_when_disabled():
    assert not should_send_auto_stop(send_stop_after_move=False, is_tilt_move=False)


def test_should_never_send_auto_stop_for_tilt_move_when_enabled():
    assert not should_send_auto_stop(send_stop_after_move=True, is_tilt_move=True)


def test_should_never_send_auto_stop_for_tilt_move_when_disabled():
    assert not should_send_auto_stop(send_stop_after_move=False, is_tilt_move=True)


def test_infer_tilt_after_cover_move_opening_sets_horizontal():
    assert infer_tilt_after_cover_move(current_position=0, target_position=50, current_tilt=0) == 100


def test_infer_tilt_after_cover_move_closing_sets_vertical():
    assert infer_tilt_after_cover_move(current_position=100, target_position=50, current_tilt=100) == 0


def test_infer_tilt_after_cover_move_without_move_keeps_current_tilt():
    assert infer_tilt_after_cover_move(current_position=50, target_position=50, current_tilt=67) == 67


def test_tilt_step_to_percent_for_7_steps():
    assert tilt_step_to_percent(0) == 0
    assert tilt_step_to_percent(1) == 17
    assert tilt_step_to_percent(2) == 33
    assert tilt_step_to_percent(3) == 50
    assert tilt_step_to_percent(4) == 67
    assert tilt_step_to_percent(5) == 83
    assert tilt_step_to_percent(6) == 100


def test_tilt_step_to_percent_clamps_out_of_range_steps():
    assert tilt_step_to_percent(-2) == 0
    assert tilt_step_to_percent(99) == 100


def test_tilt_percent_to_step_for_7_steps():
    assert tilt_percent_to_step(0) == 0
    assert tilt_percent_to_step(17) == 1
    assert tilt_percent_to_step(33) == 2
    assert tilt_percent_to_step(50) == 3
    assert tilt_percent_to_step(67) == 4
    assert tilt_percent_to_step(83) == 5
    assert tilt_percent_to_step(100) == 6


