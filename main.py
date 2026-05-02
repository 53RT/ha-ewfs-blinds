"""Tiny local demo for EWFS timing calculations."""

from custom_components.warema_ewfs.model import (
    compute_cover_duration,
    compute_tilt_duration,
    snap_to_tilt_step,
)


def main() -> None:
    cover_seconds = compute_cover_duration(current=15, target=90, time_up=28.0, time_down=24.0)
    target_tilt = snap_to_tilt_step(62)
    tilt_seconds = compute_tilt_duration(
        current_tilt=33,
        target_tilt=target_tilt,
        step_time_up=0.35,
        step_time_down=0.45,
    )

    print(f"Cover 15% -> 90%: {cover_seconds:.2f}s")
    print(f"Tilt 33% -> {target_tilt}%: {tilt_seconds:.2f}s")


if __name__ == "__main__":
    main()
