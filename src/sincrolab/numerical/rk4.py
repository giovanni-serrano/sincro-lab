"""Generic classical RK4 integration for real ordinary differential equations."""

from collections.abc import Callable
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from sincrolab.numerical._time_grid import build_time_grid

State: TypeAlias = float | NDArray[np.float64]
RhsFunction: TypeAlias = Callable[[float, State], State]


def classical_rk4(
    rhs: RhsFunction,
    y0: State,
    t_start: float,
    t_end: float,
    dt: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Integrate ``y' = rhs(t, y)`` with the classical fourth-order RK method.

    Times are one-dimensional. Scalar states have shape ``(n_times,)`` and
    vector states ``(n_times, n_states)``. A shorter final step reaches
    ``t_end`` exactly when ``dt`` does not divide the interval.
    """
    times = build_time_grid(t_start=t_start, t_end=t_end, dt=dt)
    initial_state = np.asarray(y0, dtype=np.float64)

    if initial_state.ndim > 1:
        raise ValueError("y0 must be a scalar or one-dimensional vector")
    if initial_state.ndim == 1 and initial_state.size == 0:
        raise ValueError("y0 vector must not be empty")

    states = np.empty((times.size,) + initial_state.shape, dtype=np.float64)
    states[0] = initial_state
    scalar_state = initial_state.ndim == 0

    def evaluate_rhs(time: float, state: NDArray[np.float64]) -> NDArray[np.float64]:
        state_for_rhs: State
        if scalar_state:
            state_for_rhs = float(state)
        else:
            state_for_rhs = state.copy()

        derivative = np.array(rhs(time, state_for_rhs), dtype=np.float64, copy=True)
        if derivative.shape != initial_state.shape:
            raise ValueError("rhs output shape must match y0")
        return derivative

    for index, time in enumerate(times[:-1]):
        step = times[index + 1] - time
        half_step = 0.5 * step
        current_state = np.asarray(states[index], dtype=np.float64)

        k1 = evaluate_rhs(float(time), current_state)
        k2 = evaluate_rhs(float(time + half_step), current_state + half_step * k1)
        k3 = evaluate_rhs(float(time + half_step), current_state + half_step * k2)
        k4 = evaluate_rhs(float(times[index + 1]), current_state + step * k3)

        states[index + 1] = current_state + (step / 6.0) * (
            k1 + 2.0 * k2 + 2.0 * k3 + k4
        )

    return times, states
