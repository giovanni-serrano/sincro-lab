from collections.abc import Callable

import numpy as np
import pytest

from sincrolab.numerical import classical_rk4, explicit_euler

Integrator = Callable[..., tuple[np.ndarray, np.ndarray]]
INTEGRATORS = [
    pytest.param(explicit_euler, id="euler"),
    pytest.param(classical_rk4, id="rk4"),
]


@pytest.mark.parametrize("integrator", INTEGRATORS)
def test_integrator_shortens_final_step_to_reach_t_end(
    integrator: Integrator,
) -> None:
    times, states = integrator(
        lambda _time, _state: 1.0,
        y0=0.0,
        t_start=1.0,
        t_end=2.0,
        dt=0.3,
    )

    np.testing.assert_allclose(times, [1.0, 1.3, 1.6, 1.9, 2.0])
    assert times[-1] == 2.0
    assert states[-1] == pytest.approx(1.0)


@pytest.mark.parametrize("integrator", INTEGRATORS)
def test_integrator_avoids_spurious_terminal_microstep(
    integrator: Integrator,
) -> None:
    times, states = integrator(
        lambda _time, _state: 1.0,
        y0=0.0,
        t_start=0.0,
        t_end=0.13,
        dt=0.01,
    )

    assert times.size == 14
    assert times[-1] == 0.13
    assert np.count_nonzero(times == 0.13) == 1
    assert np.all(np.diff(times) > 0.0)
    assert states[-1] == pytest.approx(0.13)


@pytest.mark.parametrize("integrator", INTEGRATORS)
def test_integrator_does_not_expose_vector_storage_to_rhs_mutation(
    integrator: Integrator,
) -> None:
    y0 = np.array([1.0, -1.0])

    def mutating_rhs(_time: float, state: np.ndarray) -> np.ndarray:
        state[:] = 100.0
        return np.zeros_like(state)

    _, states = integrator(
        mutating_rhs,
        y0=y0,
        t_start=0.0,
        t_end=0.2,
        dt=0.1,
    )

    np.testing.assert_array_equal(y0, [1.0, -1.0])
    np.testing.assert_array_equal(states, [[1.0, -1.0]] * 3)


@pytest.mark.parametrize("integrator", INTEGRATORS)
@pytest.mark.parametrize("invalid_dt", [0.0, -0.1, float("nan"), float("inf")])
def test_integrator_rejects_invalid_dt(
    integrator: Integrator,
    invalid_dt: float,
) -> None:
    with pytest.raises(ValueError, match="dt"):
        integrator(
            lambda _time, state: state,
            y0=1.0,
            t_start=0.0,
            t_end=1.0,
            dt=invalid_dt,
        )


@pytest.mark.parametrize("integrator", INTEGRATORS)
@pytest.mark.parametrize(
    ("t_start", "t_end"),
    [
        (float("nan"), 1.0),
        (float("inf"), 1.0),
        (float("-inf"), 1.0),
        (0.0, float("nan")),
        (0.0, float("inf")),
        (0.0, float("-inf")),
        (1.0, 0.0),
    ],
)
def test_integrator_rejects_invalid_time_interval(
    integrator: Integrator,
    t_start: float,
    t_end: float,
) -> None:
    with pytest.raises(ValueError):
        integrator(
            lambda _time, state: state,
            y0=1.0,
            t_start=t_start,
            t_end=t_end,
            dt=0.1,
        )


@pytest.mark.parametrize("integrator", INTEGRATORS)
@pytest.mark.parametrize(
    ("y0", "invalid_derivative"),
    [
        (1.0, np.array([1.0, 2.0])),
        (np.array([1.0, 2.0]), 1.0),
    ],
)
def test_integrator_rejects_rhs_shape_mismatch(
    integrator: Integrator,
    y0: float | np.ndarray,
    invalid_derivative: float | np.ndarray,
) -> None:
    with pytest.raises(ValueError, match="rhs output shape"):
        integrator(
            lambda _time, _state: invalid_derivative,
            y0=y0,
            t_start=0.0,
            t_end=0.1,
            dt=0.1,
        )
