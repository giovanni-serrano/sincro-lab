from dataclasses import replace

import numpy as np
import pytest

import sincrolab.application.transient as transient_module
from sincrolab.application import SMIBSimulationResult, simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


def _parameters(**overrides: float) -> SMIBParameters:
    values = {
        "H_s": 3.5,
        "D_pu": 0.0,
        "f_base_hz": 60.0,
        "Pm_pu": 0.7,
        "Pmax_pu": 1.7,
    }
    values.update(overrides)
    return SMIBParameters(**values)


def _network(**overrides: float) -> SMIBTransientNetwork:
    values = {
        "Pmax_prefault_pu": 1.2,
        "Pmax_fault_pu": 0.2,
        "Pmax_postfault_pu": 0.9,
        "t_fault_s": 0.105,
        "t_clear_s": 0.237,
    }
    values.update(overrides)
    return SMIBTransientNetwork(**values)


def _prefault_equilibrium_state(
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


def test_transient_simulation_returns_exact_event_boundaries() -> None:
    parameters = _parameters()
    network = _network()
    initial_state = _prefault_equilibrium_state(parameters, network)

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.5,
        dt_s=0.02,
    )

    assert isinstance(result, SMIBSimulationResult)
    assert result.time_s[0] == 0.0
    assert result.time_s[-1] == 0.5
    assert np.count_nonzero(result.time_s == network.t_fault_s) == 1
    assert np.count_nonzero(result.time_s == network.t_clear_s) == 1
    assert np.all(np.diff(result.time_s) > 0.0)
    assert result.time_s.shape == result.delta_rad.shape
    assert result.time_s.shape == result.omega_dev_pu.shape
    assert result.time_s.dtype == np.float64
    assert result.delta_rad.dtype == np.float64
    assert result.omega_dev_pu.dtype == np.float64
    assert not result.time_s.flags.writeable
    assert not result.delta_rad.flags.writeable
    assert not result.omega_dev_pu.flags.writeable


def test_transient_simulation_uses_three_constant_physics_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def rk4_spy(**kwargs: object) -> tuple[np.ndarray, np.ndarray]:
        rhs = kwargs["rhs"]
        y0 = np.array(kwargs["y0"], dtype=np.float64, copy=True)
        t_start = float(kwargs["t_start"])
        t_end = float(kwargs["t_end"])
        duration = t_end - t_start
        terminal_state = y0 + np.array([duration, 2.0 * duration])
        parameters = rhs.keywords["parameters"]  # type: ignore[union-attr]
        calls.append(
            {
                "rhs": rhs,
                "parameters": parameters,
                "y0": y0,
                "terminal_state": terminal_state.copy(),
                "interval": (t_start, t_end),
                "dt": kwargs["dt"],
            }
        )
        if t_start == t_end:
            return np.array([t_start]), y0[np.newaxis, :]
        return (
            np.array([t_start, t_end]),
            np.vstack([y0, terminal_state]),
        )

    monkeypatch.setattr(transient_module, "classical_rk4", rk4_spy)
    parameters = _parameters(Pmax_pu=1.7)
    network = _network()
    initial_state = SMIBInitialState(delta_rad=0.6, omega_dev_pu=0.01)

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.5,
        dt_s=0.02,
    )

    assert len(calls) == 3
    assert [call["interval"] for call in calls] == [
        (0.0, network.t_fault_s),
        (network.t_fault_s, network.t_clear_s),
        (network.t_clear_s, 0.5),
    ]
    assert [call["parameters"].Pmax_pu for call in calls] == [  # type: ignore[union-attr]
        network.Pmax_prefault_pu,
        network.Pmax_fault_pu,
        network.Pmax_postfault_pu,
    ]
    for call in calls:
        segment_parameters = call["parameters"]
        assert call["rhs"].func is smib_swing_rhs  # type: ignore[union-attr]
        assert call["dt"] == 0.02
        assert replace(  # type: ignore[arg-type]
            segment_parameters,
            Pmax_pu=parameters.Pmax_pu,
        ) == parameters

    np.testing.assert_array_equal(calls[1]["y0"], calls[0]["terminal_state"])
    np.testing.assert_array_equal(calls[2]["y0"], calls[1]["terminal_state"])
    assert np.count_nonzero(result.time_s == network.t_fault_s) == 1
    assert np.count_nonzero(result.time_s == network.t_clear_s) == 1


def test_transient_simulation_allows_events_at_horizon_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_rk4 = transient_module.classical_rk4
    intervals: list[tuple[float, float]] = []

    def rk4_spy(**kwargs: object) -> tuple[np.ndarray, np.ndarray]:
        intervals.append((float(kwargs["t_start"]), float(kwargs["t_end"])))
        return original_rk4(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(transient_module, "classical_rk4", rk4_spy)
    parameters = _parameters()
    network = _network(
        Pmax_fault_pu=0.0,
        t_fault_s=0.0,
        t_clear_s=0.3,
    )
    initial_state = _prefault_equilibrium_state(parameters, network)

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.3,
        dt_s=0.02,
    )

    assert intervals == [(0.0, 0.0), (0.0, 0.3), (0.3, 0.3)]
    assert result.time_s[0] == 0.0
    assert result.time_s[-1] == 0.3
    assert np.count_nonzero(result.time_s == 0.0) == 1
    assert np.count_nonzero(result.time_s == 0.3) == 1
    assert result.delta_rad[0] == initial_state.delta_rad
    assert result.omega_dev_pu[0] == initial_state.omega_dev_pu


@pytest.mark.parametrize(
    ("t_start_s", "t_end_s", "message"),
    [
        (0.11, 0.5, "t_start_s"),
        (0.0, 0.23, "t_end_s"),
        (float("nan"), 0.5, "finite"),
        (float("inf"), 0.5, "finite"),
        (float("-inf"), 0.5, "finite"),
        (0.0, float("nan"), "finite"),
        (0.0, float("inf"), "finite"),
        (0.0, float("-inf"), "finite"),
    ],
)
def test_transient_simulation_rejects_incompatible_horizon(
    t_start_s: float,
    t_end_s: float,
    message: str,
) -> None:
    parameters = _parameters()
    network = _network()

    with pytest.raises(ValueError, match=message):
        simulate_smib_transient(
            parameters,
            _prefault_equilibrium_state(parameters, network),
            network,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            dt_s=0.02,
        )


@pytest.mark.parametrize(
    "invalid_dt_s",
    [0.0, -0.01, float("nan"), float("inf")],
)
def test_transient_simulation_preserves_invalid_dt_contract(
    invalid_dt_s: float,
) -> None:
    parameters = _parameters()
    network = _network()

    with pytest.raises(ValueError, match="dt"):
        simulate_smib_transient(
            parameters,
            _prefault_equilibrium_state(parameters, network),
            network,
            t_start_s=0.0,
            t_end_s=0.5,
            dt_s=invalid_dt_s,
        )


def test_severe_fault_produces_positive_rotor_acceleration() -> None:
    parameters = _parameters(D_pu=0.0)
    network = _network(
        Pmax_fault_pu=0.0,
        Pmax_postfault_pu=1.2,
        t_fault_s=0.1,
        t_clear_s=0.2,
    )
    initial_state = _prefault_equilibrium_state(parameters, network)

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.25,
        dt_s=0.01,
    )
    fault_index = int(np.flatnonzero(result.time_s == network.t_fault_s)[0])
    boundary_state = np.array(
        [result.delta_rad[fault_index], result.omega_dev_pu[fault_index]]
    )
    fault_parameters = replace(parameters, Pmax_pu=network.Pmax_fault_pu)
    fault_derivatives = smib_swing_rhs(
        time_s=network.t_fault_s,
        state=boundary_state,
        parameters=fault_parameters,
    )

    assert np.max(np.abs(result.omega_dev_pu[: fault_index + 1])) <= 1e-13
    assert fault_derivatives[1] > 0.0
    assert result.omega_dev_pu[fault_index + 1] > result.omega_dev_pu[fault_index]
    assert result.delta_rad[fault_index + 1] > result.delta_rad[fault_index]


def test_equal_network_capabilities_preserve_prefault_equilibrium() -> None:
    parameters = _parameters(D_pu=0.2)
    network = _network(
        Pmax_fault_pu=1.2,
        Pmax_postfault_pu=1.2,
    )
    initial_state = _prefault_equilibrium_state(parameters, network)

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.5,
        dt_s=0.02,
    )

    assert np.max(np.abs(result.delta_rad - initial_state.delta_rad)) <= 1e-12
    assert np.max(np.abs(result.omega_dev_pu)) <= 1e-13


def test_transient_simulation_does_not_mutate_inputs() -> None:
    parameters = _parameters()
    network = _network()
    initial_state = _prefault_equilibrium_state(parameters, network)
    parameters_before = replace(parameters)
    network_before = replace(network)
    initial_state_before = replace(initial_state)

    simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=0.0,
        t_end_s=0.5,
        dt_s=0.02,
    )

    assert parameters == parameters_before
    assert network == network_before
    assert initial_state == initial_state_before
