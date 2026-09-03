"""Independent SciPy references for SincroLab numerical validation."""

from collections.abc import Callable
from functools import partial
from math import exp
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
from numpy.typing import NDArray
import pytest
from scipy.integrate import solve_ivp

import sincrolab.application as application_module
import sincrolab.application.transient as transient_module
import sincrolab.numerical as numerical_module
from sincrolab.application import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)
from sincrolab.numerical import classical_rk4

VectorRhs = Callable[[float, NDArray[np.float64]], NDArray[np.float64]]

# DOP853 provides a high-order adaptive reference for each smooth, nonstiff
# segment. These controls keep its observed error well below fixed-step RK4;
# they are numerical test settings, not estimates of physical uncertainty.
SCIPY_METHOD = "DOP853"
SCIPY_RTOL = 1e-11
SCIPY_ATOL = 1e-13


def _solve_scipy_at_times(
    rhs: VectorRhs,
    y0: NDArray[np.float64],
    time_s: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Integrate with SciPy at caller-supplied physical sample times."""
    solution = solve_ivp(
        rhs,
        (float(time_s[0]), float(time_s[-1])),
        np.asarray(y0, dtype=np.float64),
        method=SCIPY_METHOD,
        t_eval=time_s,
        rtol=SCIPY_RTOL,
        atol=SCIPY_ATOL,
    )
    if not solution.success:
        raise RuntimeError(f"SciPy solve_ivp failed: {solution.message}")

    solution_time_s = np.asarray(solution.t, dtype=np.float64)
    states = np.asarray(solution.y, dtype=np.float64).T
    expected_shape = (time_s.size, np.asarray(y0).size)
    if not np.array_equal(solution_time_s, time_s):
        raise RuntimeError("SciPy did not return the requested evaluation times")
    if states.shape != expected_shape:
        raise RuntimeError(
            f"SciPy returned state shape {states.shape}, expected {expected_shape}"
        )
    if not np.all(np.isfinite(states)):
        raise RuntimeError("SciPy returned non-finite state values")
    return states


def _scipy_transient_reference(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    network: SMIBTransientNetwork,
    evaluation_time_s: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Build a three-segment SciPy reference without SincroLab integration."""
    for event_name, event_time_s in (
        ("t_fault_s", network.t_fault_s),
        ("t_clear_s", network.t_clear_s),
    ):
        if np.count_nonzero(evaluation_time_s == event_time_s) != 1:
            raise ValueError(
                f"evaluation_time_s must contain {event_name} exactly once"
            )

    current_state = np.array(
        [initial_state.delta_rad, initial_state.omega_dev_pu],
        dtype=np.float64,
    )
    segments = (
        (
            float(evaluation_time_s[0]),
            network.t_fault_s,
            network.Pmax_prefault_pu,
        ),
        (
            network.t_fault_s,
            network.t_clear_s,
            network.Pmax_fault_pu,
        ),
        (
            network.t_clear_s,
            float(evaluation_time_s[-1]),
            network.Pmax_postfault_pu,
        ),
    )
    time_parts: list[NDArray[np.float64]] = []
    state_parts: list[NDArray[np.float64]] = []

    for segment_index, (start_s, end_s, Pmax_pu) in enumerate(segments):
        segment_time_s = evaluation_time_s[
            (evaluation_time_s >= start_s) & (evaluation_time_s <= end_s)
        ]
        if (
            segment_time_s.size < 2
            or segment_time_s[0] != start_s
            or segment_time_s[-1] != end_s
        ):
            raise ValueError(
                "evaluation_time_s must contain every segment boundary exactly"
            )
        rhs = partial(
            smib_swing_rhs,
            parameters=parameters,
            Pmax_pu=Pmax_pu,
        )
        segment_states = _solve_scipy_at_times(
            rhs,
            current_state,
            segment_time_s,
        )
        current_state = np.array(
            segment_states[-1],
            dtype=np.float64,
            copy=True,
        )
        first_sample = 0 if segment_index == 0 else 1
        time_parts.append(segment_time_s[first_sample:])
        state_parts.append(segment_states[first_sample:])

    reference_time_s = np.concatenate(time_parts)
    reference_states = np.concatenate(state_parts, axis=0)
    if not np.array_equal(reference_time_s, evaluation_time_s):
        raise RuntimeError("SciPy segment assembly changed evaluation times")
    return reference_time_s, reference_states


def _smib_parameters() -> SMIBParameters:
    return SMIBParameters(
        H_s=3.5,
        D_pu=0.2,
        f_base_hz=60.0,
        Pm_pu=0.7,
    )


def _transient_network() -> SMIBTransientNetwork:
    return SMIBTransientNetwork(
        Pmax_prefault_pu=1.2,
        Pmax_fault_pu=0.2,
        Pmax_postfault_pu=0.9,
        t_fault_s=0.105,
        t_clear_s=0.237,
    )


def _equilibrium_state(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
) -> SMIBInitialState:
    return SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=0.0,
    )


def test_scipy_and_rk4_against_analytic_exponential() -> None:
    time_s, rk4_states = classical_rk4(
        lambda _time_s, state: state,
        y0=np.array([1.0]),
        t_start=0.0,
        t_end=1.0,
        dt=0.1,
    )
    scipy_states = _solve_scipy_at_times(
        lambda _time_s, state: state,
        np.array([1.0]),
        time_s,
    )[:, 0]
    analytic_states = np.exp(time_s)

    rk4_error = float(np.max(np.abs(rk4_states[:, 0] - analytic_states)))
    scipy_error = float(np.max(np.abs(scipy_states - analytic_states)))

    assert rk4_error < 3e-6
    assert scipy_error < 1e-10
    assert scipy_error < rk4_error
    assert abs(float(rk4_states[-1, 0]) - exp(1.0)) < 3e-6
    assert abs(float(scipy_states[-1]) - exp(1.0)) < 1e-10


def test_constant_physics_smib_rk4_agrees_with_scipy() -> None:
    parameters = _smib_parameters()
    initial_state = np.array([0.67, 0.002], dtype=np.float64)
    rhs = partial(
        smib_swing_rhs,
        parameters=parameters,
        Pmax_pu=1.2,
    )
    time_s, rk4_states = classical_rk4(
        rhs,
        y0=initial_state,
        t_start=0.0,
        t_end=1.0,
        dt=0.02,
    )
    scipy_states = _solve_scipy_at_times(rhs, initial_state, time_s)

    delta_error_rad = np.abs(rk4_states[:, 0] - scipy_states[:, 0])
    omega_error_pu = np.abs(rk4_states[:, 1] - scipy_states[:, 1])

    assert float(np.max(delta_error_rad)) < 5e-6
    assert float(np.max(omega_error_pu)) < 1e-7
    assert float(delta_error_rad[-1]) < 5e-6
    assert float(omega_error_pu[-1]) < 1e-7


def test_segmented_scipy_reference_agrees_with_transient_rk4() -> None:
    parameters = _smib_parameters()
    network = _transient_network()
    initial_state = _equilibrium_state(parameters, network)
    rk4_result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.8,
        dt_s=0.02,
    )

    scipy_time_s, scipy_states = _scipy_transient_reference(
        parameters,
        initial_state,
        network,
        rk4_result.time_s,
    )
    delta_error_rad = np.abs(rk4_result.delta_rad - scipy_states[:, 0])
    omega_error_pu = np.abs(rk4_result.omega_dev_pu - scipy_states[:, 1])

    np.testing.assert_array_equal(scipy_time_s, rk4_result.time_s)
    assert np.count_nonzero(scipy_time_s == network.t_fault_s) == 1
    assert np.count_nonzero(scipy_time_s == network.t_clear_s) == 1
    assert network.t_fault_s / rk4_result.dt_s != round(
        network.t_fault_s / rk4_result.dt_s
    )
    assert network.t_clear_s / rk4_result.dt_s != round(
        network.t_clear_s / rk4_result.dt_s
    )
    assert float(np.max(delta_error_rad)) < 2e-6
    assert float(np.max(omega_error_pu)) < 1e-8
    assert float(delta_error_rad[-1]) < 2e-6
    assert float(omega_error_pu[-1]) < 1e-8


def test_scipy_reference_transports_only_scipy_segment_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("SincroLab integrators and orchestration are forbidden")

    def solve_ivp_spy(
        fun: object,
        t_span: tuple[float, float],
        y0: NDArray[np.float64],
        **kwargs: Any,
    ) -> SimpleNamespace:
        call_number = len(calls) + 1
        initial = np.array(y0, dtype=np.float64, copy=True)
        terminal = initial + np.array([call_number, -0.1 * call_number])
        t_eval = np.asarray(kwargs["t_eval"], dtype=np.float64)
        states = np.linspace(initial, terminal, t_eval.size)
        calls.append(
            {
                "fun": fun,
                "t_span": t_span,
                "y0": initial,
                "terminal": terminal,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(
            success=True,
            message="controlled success",
            t=t_eval,
            y=states.T,
        )

    monkeypatch.setattr(numerical_module, "classical_rk4", forbidden)
    monkeypatch.setattr(numerical_module, "explicit_euler", forbidden)
    monkeypatch.setattr(transient_module, "classical_rk4", forbidden)
    monkeypatch.setattr(transient_module, "simulate_smib_transient", forbidden)
    monkeypatch.setattr(application_module, "simulate_smib_transient", forbidden)
    monkeypatch.setattr(sys.modules[__name__], "solve_ivp", solve_ivp_spy)
    parameters = _smib_parameters()
    network = _transient_network()
    initial_state = _equilibrium_state(parameters, network)
    time_s = np.array(
        [0.0, 0.05, 0.105, 0.2, 0.237, 0.3, 0.5],
        dtype=np.float64,
    )

    reference_time_s, _ = _scipy_transient_reference(
        parameters,
        initial_state,
        network,
        time_s,
    )

    assert len(calls) == 3
    np.testing.assert_array_equal(calls[1]["y0"], calls[0]["terminal"])
    np.testing.assert_array_equal(calls[2]["y0"], calls[1]["terminal"])
    assert [call["fun"].keywords["Pmax_pu"] for call in calls] == [
        network.Pmax_prefault_pu,
        network.Pmax_fault_pu,
        network.Pmax_postfault_pu,
    ]
    assert all(call["fun"].func is smib_swing_rhs for call in calls)
    assert all(call["kwargs"]["method"] == SCIPY_METHOD for call in calls)
    assert all(call["kwargs"]["rtol"] == SCIPY_RTOL for call in calls)
    assert all(call["kwargs"]["atol"] == SCIPY_ATOL for call in calls)
    np.testing.assert_array_equal(reference_time_s, time_s)
    assert np.count_nonzero(reference_time_s == network.t_fault_s) == 1
    assert np.count_nonzero(reference_time_s == network.t_clear_s) == 1


def test_rk4_refinement_reduces_error_against_scipy() -> None:
    parameters = _smib_parameters()
    initial_state = np.array([0.67, 0.002], dtype=np.float64)
    rhs = partial(
        smib_swing_rhs,
        parameters=parameters,
        Pmax_pu=1.2,
    )
    final_delta_errors_rad: list[float] = []

    for dt_s in (0.04, 0.02):
        time_s, rk4_states = classical_rk4(
            rhs,
            y0=initial_state,
            t_start=0.0,
            t_end=1.0,
            dt=dt_s,
        )
        scipy_states = _solve_scipy_at_times(rhs, initial_state, time_s)
        final_delta_errors_rad.append(
            abs(float(rk4_states[-1, 0] - scipy_states[-1, 0]))
        )

    coarse_error_rad, fine_error_rad = final_delta_errors_rad
    assert fine_error_rad < coarse_error_rad
    assert fine_error_rad < coarse_error_rad / 8.0


def test_scipy_transient_reference_is_deterministic() -> None:
    parameters = _smib_parameters()
    network = _transient_network()
    initial_state = _equilibrium_state(parameters, network)
    evaluation_time_s = np.array(
        [0.0, 0.05, 0.105, 0.2, 0.237, 0.3, 0.5],
        dtype=np.float64,
    )

    first = _scipy_transient_reference(
        parameters,
        initial_state,
        network,
        evaluation_time_s,
    )
    second = _scipy_transient_reference(
        parameters,
        initial_state,
        network,
        evaluation_time_s,
    )

    np.testing.assert_array_equal(first[0], second[0])
    np.testing.assert_array_equal(first[1], second[1])


def test_scipy_reference_reports_solver_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys.modules[__name__],
        "solve_ivp",
        lambda *args, **kwargs: SimpleNamespace(
            success=False,
            message="controlled solver failure",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="SciPy solve_ivp failed: controlled solver failure",
    ):
        _solve_scipy_at_times(
            lambda _time_s, state: state,
            np.array([1.0]),
            np.array([0.0, 1.0]),
        )
