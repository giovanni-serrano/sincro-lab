from math import cos, e, sin

import numpy as np
import pytest

from sincrolab.numerical import classical_rk4, explicit_euler


def test_classical_rk4_integrates_scalar_exponential() -> None:
    times, states = classical_rk4(
        lambda _time, state: state,
        y0=1.0,
        t_start=0.0,
        t_end=1.0,
        dt=0.1,
    )

    expected_first_step = 1.0 + 0.1 + 0.1**2 / 2.0 + 0.1**3 / 6.0 + 0.1**4 / 24.0
    np.testing.assert_allclose(times, np.linspace(0.0, 1.0, 11))
    assert states.shape == times.shape
    assert states[1] == pytest.approx(expected_first_step)
    assert states[-1] == pytest.approx(e, abs=3e-6)


def test_classical_rk4_integrates_vector_system_with_known_solution() -> None:
    y0 = np.array([1.0, 0.0])

    def oscillator_rhs(_time: float, state: np.ndarray) -> np.ndarray:
        return np.array([state[1], -state[0]])

    times, states = classical_rk4(
        oscillator_rhs,
        y0=y0,
        t_start=0.0,
        t_end=1.0,
        dt=0.1,
    )

    assert states.shape == (times.size, 2)
    np.testing.assert_allclose(states[-1], [cos(1.0), -sin(1.0)], atol=1e-5)
    np.testing.assert_array_equal(y0, [1.0, 0.0])


def test_classical_rk4_is_more_accurate_than_euler_at_same_dt() -> None:
    integration_args = {
        "rhs": lambda _time, state: state,
        "y0": 1.0,
        "t_start": 0.0,
        "t_end": 1.0,
        "dt": 0.2,
    }

    _, euler_states = explicit_euler(**integration_args)
    _, rk4_states = classical_rk4(**integration_args)

    euler_error = abs(float(euler_states[-1]) - e)
    rk4_error = abs(float(rk4_states[-1]) - e)
    assert rk4_error < euler_error


def test_classical_rk4_copies_reused_rhs_output_buffer() -> None:
    derivative_buffer = np.empty(1)

    def buffered_rhs(_time: float, state: np.ndarray) -> np.ndarray:
        derivative_buffer[:] = state
        return derivative_buffer

    _, states = classical_rk4(
        buffered_rhs,
        y0=np.array([1.0]),
        t_start=0.0,
        t_end=0.1,
        dt=0.1,
    )

    expected = 1.0 + 0.1 + 0.1**2 / 2.0 + 0.1**3 / 6.0 + 0.1**4 / 24.0
    assert states[-1, 0] == pytest.approx(expected)


def test_classical_rk4_validates_rhs_shape_at_every_stage() -> None:
    call_count = 0

    def invalid_second_stage(_time: float, state: float) -> float | np.ndarray:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return np.array([state, state])
        return state

    with pytest.raises(ValueError, match="rhs output shape"):
        classical_rk4(
            invalid_second_stage,
            y0=1.0,
            t_start=0.0,
            t_end=0.1,
            dt=0.1,
        )
