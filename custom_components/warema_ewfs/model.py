"""Pure helpers for EWFS movement and tilt timing."""

from __future__ import annotations


def clamp_percent(value: float) -> int:
    """Clamp a value to integer 0..100."""
    return max(0, min(100, int(round(value))))


def compute_cover_duration(current: int, target: int, time_up: float, time_down: float) -> float:
    """Return seconds needed for moving between cover positions."""
    if current == target:
        return 0.0
    delta = abs(target - current) / 100.0
    return delta * (time_up if target > current else time_down)


def snap_to_tilt_step(tilt_position: int, step_count: int = 7) -> int:
    """Snap an arbitrary tilt position to one of the configured discrete steps."""
    if step_count <= 1:
        return clamp_percent(tilt_position)

    index = round((clamp_percent(tilt_position) / 100.0) * (step_count - 1))
    return clamp_percent((index / (step_count - 1)) * 100)


def compute_tilt_duration(
    current_tilt: int,
    target_tilt: int,
    step_time_up: float,
    step_time_down: float,
    step_count: int = 7,
) -> float:
    """Return seconds needed between discrete tilt positions."""
    if step_count <= 1:
        return 0.0

    current_step = round((clamp_percent(current_tilt) / 100.0) * (step_count - 1))
    target_step = round((clamp_percent(target_tilt) / 100.0) * (step_count - 1))

    if current_step == target_step:
        return 0.0

    step_delta = abs(target_step - current_step)
    return step_delta * (step_time_up if target_step > current_step else step_time_down)


def should_send_auto_stop(send_stop_after_move: bool, is_tilt_move: bool) -> bool:
    """Return whether an automatic stop command should be sent after movement."""
    return send_stop_after_move and not is_tilt_move


def infer_tilt_after_cover_move(current_position: int, target_position: int, current_tilt: int) -> int:
    """Infer tilt after a normal move based on direction.

    Upward movement leaves slats horizontal (100), downward movement vertical (0).
    """
    if target_position > current_position:
        return 100
    if target_position < current_position:
        return 0
    return clamp_percent(current_tilt)


def tilt_step_to_percent(step: int, step_count: int = 7) -> int:
    """Convert a discrete tilt step to a snapped percent value."""
    if step_count <= 1:
        return 0
    bounded = max(0, min(step_count - 1, int(step)))
    return clamp_percent((bounded / (step_count - 1)) * 100)


def tilt_percent_to_step(tilt_percent: int, step_count: int = 7) -> int:
    """Convert a tilt percent value to the nearest discrete step index."""
    if step_count <= 1:
        return 0
    return round((clamp_percent(tilt_percent) / 100.0) * (step_count - 1))


