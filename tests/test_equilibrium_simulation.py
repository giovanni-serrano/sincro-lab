from dataclasses import replace

import numpy as np
import pytest

import sincrolab.application.equilibrium as equilibrium_module
from sincrolab.application import SMIBSimulationResult, simulate_smib_equilibrium
from sincrolab.models import (
    SMIBParameters,
    electrical_power_pu,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)

PMAX_PU = 1.2


def _parameters(**overrides: float) -> SMIBParameters:
    values = {
        "H_s": 3.5,
        "D_pu": 0.2,
        "f_base_hz": 60.0,
        "Pm_pu": 0.7,
    }
    values.update(overrides)
    return SMIBParameters(**values)


def test_equilibrium_simulation_returns_structured_equilibrium_trajectory() -> None:
    parameters = _parameters()
    result = simulate_smib_equilibrium(
        parameters,
        Pmax_pu=PMAX_PU,
        t_start_s=1.0,
        t_end_s=2.0,
        dt_s=1.0 / 64.0,
    )
    expected_delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=PMAX_PU,
    )

    assert isinstance(result, SMIBSimulationResult)
    assert result.time_s.ndim == 1
    assert result.delta_rad.ndim == 1
    assert result.omega_dev_pu.ndim == 1
    assert result.time_s.dtype == np.float64
    assert result.delta_rad.dtype == np.float64
    assert result.omega_dev_pu.dtype == np.float64
    assert result.time_s.shape == result.delta_rad.shape
    assert result.time_s.shape == result.omega_dev_pu.shape
    assert result.time_s[0] == 1.0
    assert result.time_s[-1] == 2.0
    assert result.delta_rad[0] == pytest.approx(expected_delta0_rad)
    assert result.omega_dev_pu[0] == 0.0

    initial_Pe_pu = electrical_power_pu(
        delta_rad=result.delta_rad[0],
        Pmax_pu=PMAX_PU,
    )
    initial_derivatives = smib_swing_rhs(
        time_s=result.time_s[0],
        state=np.array([result.delta_rad[0], result.omega_dev_pu[0]]),
        parameters=parameters,
        Pmax_pu=PMAX_PU,
    )
    # libm implementations may differ by several ULP in the asin/sin round
    # trip; 1e-14 remains a roundoff-scale tolerance for O(1) pu powers.
    roundoff_atol = 1e-14
    assert initial_Pe_pu == pytest.approx(
        parameters.Pm_pu,
        rel=0.0,
        abs=roundoff_atol,
    )
    np.testing.assert_allclose(
        initial_derivatives,
        [0.0, 0.0],
        rtol=0.0,
        atol=roundoff_atol,
    )


def test_equilibrium_simulation_preserves_equilibrium_with_roundoff_bounds() -> None:
    parameters = _parameters()
    result = simulate_smib_equilibrium(
        parameters,
        Pmax_pu=PMAX_PU,
        t_start_s=0.0,
        t_end_s=10.0,
        dt_s=1.0 / 64.0,
    )
    delta0_rad = result.delta_rad[0]

    max_delta_drift_rad = float(np.max(np.abs(result.delta_rad - delta0_rad)))
    max_abs_omega_dev_pu = float(np.max(np.abs(result.omega_dev_pu)))

    # The 640 steps evaluate 2,560 RK4 stages. These limits allow accumulated
    # float64 roundoff while remaining negligible on the O(1) state scales.
    assert max_delta_drift_rad <= 1e-12
    assert max_abs_omega_dev_pu <= 1e-13


@pytest.mark.parametrize(
    ("t_start_s", "t_end_s", "dt_s"),
    [
        (0.0, 1.0, 0.0),
        (1.0, 0.0, 0.1),
    ],
)
def test_equilibrium_simulation_delegates_invalid_time_contract(
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> None:
    with pytest.raises(ValueError):
        simulate_smib_equilibrium(
            _parameters(),
            Pmax_pu=PMAX_PU,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            dt_s=dt_s,
        )


def test_equilibrium_simulation_does_not_mutate_parameters() -> None:
    parameters = _parameters()
    parameters_before = replace(parameters)

    simulate_smib_equilibrium(
        parameters,
        Pmax_pu=PMAX_PU,
        t_start_s=0.0,
        t_end_s=1.0,
        dt_s=1.0 / 64.0,
    )

    assert parameters == parameters_before


def test_equilibrium_simulation_preserves_missing_equilibrium_error() -> None:
    parameters = _parameters(Pm_pu=1.3)

    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        simulate_smib_equilibrium(
            parameters,
            Pmax_pu=PMAX_PU,
            t_start_s=0.0,
            t_end_s=1.0,
            dt_s=0.1,
        )


def test_equilibrium_simulation_uses_classical_rk4(monkeypatch: pytest.MonkeyPatch) -> None:
    original_rk4 = equilibrium_module.classical_rk4
    calls: list[dict[str, object]] = []

    def rk4_spy(*args: object, **kwargs: object) -> tuple[np.ndarray, np.ndarray]:
        calls.append(kwargs)
        return original_rk4(*args, **kwargs)

    monkeypatch.setattr(equilibrium_module, "classical_rk4", rk4_spy)
    parameters = _parameters()
    simulate_smib_equilibrium(
        parameters,
        Pmax_pu=PMAX_PU,
        t_start_s=1.0,
        t_end_s=2.0,
        dt_s=1.0 / 64.0,
    )

    assert len(calls) == 1
    call = calls[0]
    expected_delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=PMAX_PU,
    )
    np.testing.assert_allclose(call["y0"], [expected_delta0_rad, 0.0])
    assert call["t_start"] == 1.0
    assert call["t_end"] == 2.0
    assert call["dt"] == 1.0 / 64.0
