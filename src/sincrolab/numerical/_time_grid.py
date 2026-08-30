"""Shared time-grid construction for fixed-step integrators."""

from math import isclose, isfinite

import numpy as np
from numpy.typing import NDArray


def build_time_grid(
    t_start: float,
    t_end: float,
    dt: float,
) -> NDArray[np.float64]:
    """Build a fixed-step grid with an optional shorter final step."""
    if not isfinite(t_start) or not isfinite(t_end):
        raise ValueError("t_start and t_end must be finite")
    if not isfinite(dt) or dt <= 0.0:
        raise ValueError("dt must be finite and greater than zero")
    if t_end < t_start:
        raise ValueError("t_end must be greater than or equal to t_start")

    times = [float(t_start)]
    # Floating accumulation can leave the remainder a few ULP above dt;
    # treating it as one full step avoids a spurious near-zero final step.
    relative_tolerance = 8.0 * np.finfo(np.float64).eps

    while times[-1] < t_end:
        current_time = times[-1]
        remaining = t_end - current_time
        reaches_end = remaining < dt or isclose(
            remaining,
            dt,
            rel_tol=relative_tolerance,
            abs_tol=0.0,
        )
        next_time = t_end if reaches_end else current_time + dt

        if next_time <= current_time:
            raise ValueError("dt is too small to advance time at this scale")

        times.append(float(next_time))

    return np.asarray(times, dtype=np.float64)
