"""Generic explicit Euler integration for real ordinary differential equations."""

from collections.abc import Callable
from math import isclose, isfinite
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

State: TypeAlias = float | NDArray[np.float64]
RhsFunction: TypeAlias = Callable[[float, State], State]


def explicit_euler(
    rhs: RhsFunction,
    y0: State,
    t_start: float,
    t_end: float,
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Integrate ``y' = rhs(t, y)`` with the explicit Euler method.

    Times are one-dimensional. Scalar states have shape ``(n_times,)`` and
    vector states ``(n_times, n_states)``. A shorter final step reaches
    ``t_end`` exactly when ``dt`` does not divide the interval.
    """
    times = _build_time_grid(t_start=t_start, t_end=t_end, dt=dt)
    initial_state = np.asarray(y0, dtype=np.float64)

    if initial_state.ndim > 1:
        raise ValueError("y0 must be a scalar or one-dimensional vector")
    if initial_state.ndim == 1 and initial_state.size == 0:
        raise ValueError("y0 vector must not be empty")

    states = np.empty((times.size,) + initial_state.shape, dtype=np.float64)
    states[0] = initial_state
    scalar_state = initial_state.ndim == 0

    for index, time in enumerate(times[:-1]):
        state_for_rhs: State
        if scalar_state:
            state_for_rhs = float(states[index])
        else:
            state_for_rhs = states[index].copy()

        derivative = np.asarray(rhs(float(time), state_for_rhs), dtype=np.float64)
        if derivative.shape != initial_state.shape:
            raise ValueError("rhs output shape must match y0")

        step = times[index + 1] - time
        states[index + 1] = states[index] + step * derivative

    return times, states


def _build_time_grid(
    t_start: float,
    t_end: float,
    dt: float,
) -> NDArray[np.float64]:
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
