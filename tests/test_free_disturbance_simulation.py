from dataclasses import replace
from math import cos

import numpy as np
import pytest

from sincrolab.application import (
    SMIBSimulationResult,
    simulate_smib_equilibrium,
    simulate_smib_free_disturbance,
)
from sincrolab.models import (
    SMIBParameters,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)

DELTA_OFFSET_RAD = 0.05
DT_S = 1.0 / 128.0
T_END_S = 10.0
PMAX_PU = 1.2


def _parameters(**overrides: float) -> SMIBParameters:
    values = {
        "H_s": 3.5,
        "D_pu": 0.0,
        "f_base_hz": 60.0,
        "Pm_pu": 0.7,
    }
    values.update(overrides)
    return SMIBParameters(**values)


def _window_max_abs(
    time_s: np.ndarray,
    values: np.ndarray,
    *,
    t_min_s: float,
    t_max_s: float,
) -> float:
    mask = (time_s >= t_min_s) & (time_s <= t_max_s)
    return float(np.max(np.abs(values[mask])))


def _count_sign_changes(values: np.ndarray, deadband: float) -> int:
    meaningful_signs = np.sign(values[np.abs(values) > deadband])
    return int(np.count_nonzero(meaningful_signs[1:] != meaningful_signs[:-1]))


def test_zero_offset_reproduces_equilibrium_simulation() -> None:
    parameters = _parameters(D_pu=0.2)
    simulation_args = {
        "t_start_s": 0.0,
        "t_end_s": 2.0,
        "dt_s": DT_S,
    }

    equilibrium = simulate_smib_equilibrium(
        parameters,
        Pmax_pu=PMAX_PU,
        **simulation_args,
    )
    disturbed = simulate_smib_free_disturbance(
        parameters,
        Pmax_pu=PMAX_PU,
        delta_offset_rad=0.0,
        **simulation_args,
    )

    assert isinstance(disturbed, SMIBSimulationResult)
    np.testing.assert_allclose(
        disturbed.time_s,
        equilibrium.time_s,
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_allclose(
        disturbed.delta_rad,
        equilibrium.delta_rad,
        rtol=0.0,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        disturbed.omega_dev_pu,
        equilibrium.omega_dev_pu,
        rtol=0.0,
        atol=1e-14,
    )


@pytest.mark.parametrize(
    ("delta_offset_rad", "restoring_sign"),
    [
        (DELTA_OFFSET_RAD, -1.0),
        (-DELTA_OFFSET_RAD, 1.0),
    ],
)
def test_initial_acceleration_restores_toward_stable_equilibrium(
    delta_offset_rad: float,
    restoring_sign: float,
) -> None:
    parameters = _parameters()
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=PMAX_PU,
    )
    result = simulate_smib_free_disturbance(
        parameters,
        Pmax_pu=PMAX_PU,
        delta_offset_rad=delta_offset_rad,
        t_start_s=0.0,
        t_end_s=DT_S,
        dt_s=DT_S,
    )
    initial_state = np.array([result.delta_rad[0], result.omega_dev_pu[0]])
    initial_derivatives = smib_swing_rhs(
        time_s=result.time_s[0],
        state=initial_state,
        parameters=parameters,
        Pmax_pu=PMAX_PU,
    )

    assert PMAX_PU * cos(delta0_rad) > 0.0
    assert result.delta_rad[0] - delta0_rad == pytest.approx(delta_offset_rad)
    assert result.omega_dev_pu[0] == 0.0
    assert restoring_sign * initial_derivatives[1] > 0.0
    assert restoring_sign * result.omega_dev_pu[1] > 0.0


def test_undamped_response_oscillates_with_conserved_amplitude() -> None:
    parameters = _parameters(D_pu=0.0)
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=PMAX_PU,
    )
    result = simulate_smib_free_disturbance(
        parameters,
        Pmax_pu=PMAX_PU,
        delta_offset_rad=DELTA_OFFSET_RAD,
        t_start_s=0.0,
        t_end_s=T_END_S,
        dt_s=DT_S,
    )
    deviation_rad = result.delta_rad - delta0_rad
    early_amplitude_rad = _window_max_abs(
        result.time_s,
        deviation_rad,
        t_min_s=0.0,
        t_max_s=2.0,
    )
    late_amplitude_rad = _window_max_abs(
        result.time_s,
        deviation_rad,
        t_min_s=8.0,
        t_max_s=10.0,
    )
    amplitude_ratio = late_amplitude_rad / early_amplitude_rad
    crossing_count = _count_sign_changes(
        deviation_rad,
        deadband=abs(DELTA_OFFSET_RAD) * 1e-3,
    )

    assert result.time_s.shape == result.delta_rad.shape
    assert result.time_s.shape == result.omega_dev_pu.shape
    assert crossing_count >= 4
    assert np.min(deviation_rad) < -0.9 * DELTA_OFFSET_RAD
    assert np.max(np.abs(deviation_rad)) <= 1.01 * abs(DELTA_OFFSET_RAD)
    assert 0.995 <= amplitude_ratio <= 1.005
    assert np.max(np.abs(result.omega_dev_pu)) > 0.0


def test_damped_response_has_decaying_angle_and_speed_envelopes() -> None:
    parameters = _parameters(D_pu=1.0)
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=PMAX_PU,
    )
    result = simulate_smib_free_disturbance(
        parameters,
        Pmax_pu=PMAX_PU,
        delta_offset_rad=DELTA_OFFSET_RAD,
        t_start_s=0.0,
        t_end_s=T_END_S,
        dt_s=DT_S,
    )
    deviation_rad = result.delta_rad - delta0_rad
    early_angle_amplitude = _window_max_abs(
        result.time_s,
        deviation_rad,
        t_min_s=0.0,
        t_max_s=2.0,
    )
    late_angle_amplitude = _window_max_abs(
        result.time_s,
        deviation_rad,
        t_min_s=8.0,
        t_max_s=10.0,
    )
    early_speed_amplitude = _window_max_abs(
        result.time_s,
        result.omega_dev_pu,
        t_min_s=0.0,
        t_max_s=2.0,
    )
    late_speed_amplitude = _window_max_abs(
        result.time_s,
        result.omega_dev_pu,
        t_min_s=8.0,
        t_max_s=10.0,
    )
    crossing_count = _count_sign_changes(
        deviation_rad,
        deadband=abs(DELTA_OFFSET_RAD) * 1e-3,
    )

    assert crossing_count >= 4
    assert late_angle_amplitude < 0.7 * early_angle_amplitude
    assert late_speed_amplitude < 0.7 * early_speed_amplitude


def test_free_disturbance_does_not_mutate_parameters() -> None:
    parameters = _parameters(D_pu=1.0)
    parameters_before = replace(parameters)

    simulate_smib_free_disturbance(
        parameters,
        Pmax_pu=PMAX_PU,
        delta_offset_rad=DELTA_OFFSET_RAD,
        t_start_s=0.0,
        t_end_s=1.0,
        dt_s=DT_S,
    )

    assert parameters == parameters_before


@pytest.mark.parametrize(
    "invalid_offset_rad",
    [float("nan"), float("inf"), float("-inf")],
)
def test_free_disturbance_rejects_nonfinite_offset(
    invalid_offset_rad: float,
) -> None:
    with pytest.raises(ValueError, match="delta_offset_rad must be finite"):
        simulate_smib_free_disturbance(
            _parameters(),
            Pmax_pu=PMAX_PU,
            delta_offset_rad=invalid_offset_rad,
            t_start_s=0.0,
            t_end_s=1.0,
            dt_s=DT_S,
        )


def test_free_disturbance_preserves_missing_equilibrium_error() -> None:
    parameters = _parameters(Pm_pu=1.3)

    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        simulate_smib_free_disturbance(
            parameters,
            Pmax_pu=PMAX_PU,
            delta_offset_rad=DELTA_OFFSET_RAD,
            t_start_s=0.0,
            t_end_s=1.0,
            dt_s=DT_S,
        )
