from collections.abc import Callable
from math import exp, log

import numpy as np
import pytest

from sincrolab.numerical import classical_rk4, explicit_euler

Integrator = Callable[..., tuple[np.ndarray, np.ndarray]]
# Dyadic steps divide [0, 1] exactly and remain above the regime where float64
# roundoff would mask the methods' truncation error.
STEP_SIZES = (0.25, 0.125, 0.0625, 0.03125)


def _final_errors(integrator: Integrator) -> list[float]:
    """Measure final errors for y'=y+t, y(0)=1, with y=2*exp(t)-t-1."""
    exact_final_state = 2.0 * exp(1.0) - 2.0
    return [
        abs(
            float(
                integrator(
                    lambda time, state: state + time,
                    y0=1.0,
                    t_start=0.0,
                    t_end=1.0,
                    dt=dt,
                )[1][-1]
            )
            - exact_final_state
        )
        for dt in STEP_SIZES
    ]


def _observed_orders(errors: list[float]) -> list[float]:
    return [
        log(coarse_error / fine_error) / log(coarse_dt / fine_dt)
        for coarse_dt, fine_dt, coarse_error, fine_error in zip(
            STEP_SIZES[:-1],
            STEP_SIZES[1:],
            errors[:-1],
            errors[1:],
            strict=True,
        )
    ]


@pytest.mark.parametrize(
    ("integrator", "order_bounds"),
    [
        pytest.param(explicit_euler, (0.8, 1.1), id="euler-order-1"),
        pytest.param(classical_rk4, (3.7, 4.2), id="rk4-order-4"),
    ],
)
def test_observed_global_convergence_order(
    integrator: Integrator,
    order_bounds: tuple[float, float],
) -> None:
    errors = _final_errors(integrator)
    orders = _observed_orders(errors)

    assert all(
        fine_error < coarse_error
        for coarse_error, fine_error in zip(errors[:-1], errors[1:], strict=True)
    )
    lower_bound, upper_bound = order_bounds
    # Moderate steps retain truncation-error dominance. The broad bounds admit
    # pre-asymptotic variation while separating first- and fourth-order methods.
    assert all(lower_bound < order < upper_bound for order in orders)
