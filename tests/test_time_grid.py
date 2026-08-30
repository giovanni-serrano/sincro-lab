from math import ulp

import numpy as np
import pytest

from sincrolab.numerical._time_grid import build_time_grid


@pytest.mark.parametrize(
    ("t_end", "dt", "expected_size"),
    [
        (0.13, 0.01, 14),
        (10.0, 0.01, 1001),
        (0.33, 0.03, 12),
    ],
)
def test_divisible_interval_has_no_terminal_microstep(
    t_end: float,
    dt: float,
    expected_size: int,
) -> None:
    times = build_time_grid(t_start=0.0, t_end=t_end, dt=dt)
    steps = np.diff(times)

    assert times.size == expected_size
    assert times[0] == 0.0
    assert times[-1] == t_end
    assert np.count_nonzero(times == t_end) == 1
    assert np.all(steps > 0.0)
    np.testing.assert_allclose(
        steps,
        dt,
        rtol=0.0,
        atol=2.0 * ulp(t_end),
    )


def test_divisible_interval_from_nonzero_start_has_no_terminal_microstep() -> None:
    times = build_time_grid(t_start=0.1, t_end=0.43, dt=0.03)
    steps = np.diff(times)

    assert times.size == 12
    assert times[0] == 0.1
    assert times[-1] == 0.43
    assert np.count_nonzero(times == 0.43) == 1
    assert np.all(steps > 0.0)
    np.testing.assert_allclose(
        steps,
        0.03,
        rtol=0.0,
        atol=2.0 * ulp(0.43),
    )


def test_nondivisible_interval_preserves_legitimate_short_final_step() -> None:
    times = build_time_grid(t_start=0.0, t_end=0.135, dt=0.01)
    steps = np.diff(times)

    assert times.size == 15
    assert times[-1] == 0.135
    assert np.count_nonzero(times == 0.135) == 1
    assert np.all(steps > 0.0)
    assert steps[-1] < 0.01
    assert steps[-1] == pytest.approx(0.005, rel=0.0, abs=1e-15)


def test_nondivisible_interval_from_nonzero_start_preserves_remainder() -> None:
    times = build_time_grid(t_start=0.1, t_end=0.235, dt=0.01)
    steps = np.diff(times)

    assert times.size == 15
    assert times[0] == 0.1
    assert times[-1] == 0.235
    assert np.count_nonzero(times == 0.235) == 1
    assert np.all(steps > 0.0)
    assert steps[-1] < 0.01
    assert steps[-1] == pytest.approx(0.005, rel=0.0, abs=1e-15)


@pytest.mark.parametrize(
    ("t_end", "dt"),
    [
        (0.01, 0.01),
        (0.005, 0.01),
    ],
)
def test_interval_no_larger_than_dt_contains_only_both_endpoints(
    t_end: float,
    dt: float,
) -> None:
    times = build_time_grid(t_start=0.0, t_end=t_end, dt=dt)

    np.testing.assert_array_equal(times, [0.0, t_end])
