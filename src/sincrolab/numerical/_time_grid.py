"""Shared time-grid construction for fixed-step integrators."""

from math import isclose, isfinite, ulp

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
    step_index = 1

    while times[-1] < t_end:
        # Indexing from t_start prevents the rounding drift caused by adding
        # dt repeatedly. Two endpoint ULPs cover the rounding of one
        # multiplication and one addition without growing with the horizon.
        candidate_time = float(t_start + step_index * dt)
        if candidate_time <= times[-1]:
            raise ValueError("dt is too small to advance time at this scale")

        endpoint_tolerance = 2.0 * max(ulp(candidate_time), ulp(t_end))
        reaches_end = candidate_time >= t_end or isclose(
            candidate_time,
            t_end,
            rel_tol=0.0,
            abs_tol=endpoint_tolerance,
        )
        times.append(float(t_end if reaches_end else candidate_time))
        step_index += 1

    return np.asarray(times, dtype=np.float64)
