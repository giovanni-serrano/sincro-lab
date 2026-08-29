from math import e

import numpy as np
import pytest

from sincrolab.numerical import explicit_euler


def test_explicit_euler_integrates_scalar_exponential() -> None:
    times, states = explicit_euler(
        lambda _time, state: state,
        y0=1.0,
        t_start=0.0,
        t_end=1.0,
        dt=0.1,
    )

    np.testing.assert_allclose(times, np.linspace(0.0, 1.0, 11))
    assert states.shape == times.shape
    assert states[-1] == pytest.approx(1.1**10)


def test_explicit_euler_integrates_vector_system() -> None:
    y0 = np.array([1.0, 0.0])

    def oscillator_rhs(_time: float, state: np.ndarray) -> np.ndarray:
        return np.array([state[1], -state[0]])

    times, states = explicit_euler(
        oscillator_rhs,
        y0=y0,
        t_start=0.0,
        t_end=0.2,
        dt=0.1,
    )

    np.testing.assert_allclose(times, [0.0, 0.1, 0.2])
    np.testing.assert_allclose(
        states,
        [
            [1.0, 0.0],
            [1.0, -0.1],
            [0.99, -0.2],
        ],
    )
    np.testing.assert_array_equal(y0, [1.0, 0.0])


def test_exponential_final_error_decreases_with_smaller_dt() -> None:
    expected_final_errors = {
        0.2: 0.229961828459045,
        0.1: 0.124539368359045,
    }
    measured_final_errors: dict[float, float] = {}

    for dt, expected_final_error in expected_final_errors.items():
        _, states = explicit_euler(
            lambda _time, state: state,
            y0=1.0,
            t_start=0.0,
            t_end=1.0,
            dt=dt,
        )
        measured_final_errors[dt] = abs(float(states[-1]) - e)
        assert measured_final_errors[dt] == pytest.approx(
            expected_final_error,
            abs=1e-12,
        )

    assert measured_final_errors[0.1] < measured_final_errors[0.2]


def test_explicit_euler_shortens_final_step_to_reach_t_end() -> None:
    times, states = explicit_euler(
        lambda _time, _state: 1.0,
        y0=0.0,
        t_start=0.0,
        t_end=1.0,
        dt=0.3,
    )

    np.testing.assert_allclose(times, [0.0, 0.3, 0.6, 0.9, 1.0])
    assert states[-1] == pytest.approx(1.0)


@pytest.mark.parametrize("invalid_dt", [0.0, -0.1, float("nan"), float("inf")])
def test_explicit_euler_rejects_invalid_dt(invalid_dt: float) -> None:
    with pytest.raises(ValueError, match="dt"):
        explicit_euler(
            lambda _time, state: state,
            y0=1.0,
            t_start=0.0,
            t_end=1.0,
            dt=invalid_dt,
        )


def test_explicit_euler_rejects_reversed_interval() -> None:
    with pytest.raises(ValueError, match="t_end"):
        explicit_euler(
            lambda _time, state: state,
            y0=1.0,
            t_start=1.0,
            t_end=0.0,
            dt=0.1,
        )


def test_explicit_euler_rejects_rhs_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="rhs output shape"):
        explicit_euler(
            lambda _time, _state: np.array([1.0, 2.0]),
            y0=1.0,
            t_start=0.0,
            t_end=0.1,
            dt=0.1,
        )
