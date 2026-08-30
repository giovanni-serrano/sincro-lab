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
