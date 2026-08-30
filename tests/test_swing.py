from math import pi

import numpy as np
import pytest

from sincrolab.models import (
    SMIBParameters,
    electrical_power_pu,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


def _parameters(**overrides: float) -> SMIBParameters:
    values = {
        "H_s": 3.5,
        "D_pu": 0.1,
        "f_base_hz": 60.0,
        "Pm_pu": 0.8,
        "Pmax_pu": 2.0,
    }
    values.update(overrides)
    return SMIBParameters(**values)


def test_smib_swing_rhs_is_zero_at_equilibrium() -> None:
    parameters = _parameters(Pm_pu=1.0, Pmax_pu=2.0)
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=parameters.Pmax_pu,
    )

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=np.array([delta0_rad, 0.0]),
        parameters=parameters,
    )

    assert derivatives.shape == (2,)
    assert derivatives.dtype == np.float64
    np.testing.assert_allclose(derivatives, [0.0, 0.0], atol=1e-12)


def test_smib_swing_rhs_converts_speed_deviation_to_angle_rate() -> None:
    parameters = _parameters(D_pu=0.0, Pm_pu=0.0)
    omega_dev_pu = 0.01

    derivatives = smib_swing_rhs(
        time_s=1.0,
        state=np.array([0.0, omega_dev_pu]),
        parameters=parameters,
    )

    expected_d_delta_rad_dt = 2.0 * pi * parameters.f_base_hz * omega_dev_pu
    assert derivatives[0] == pytest.approx(expected_d_delta_rad_dt)


def test_smib_swing_rhs_has_positive_acceleration_when_pm_exceeds_pe() -> None:
    parameters = _parameters(Pm_pu=0.8, Pmax_pu=2.0, D_pu=0.0)

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=np.array([0.0, 0.0]),
        parameters=parameters,
    )

    assert derivatives[1] > 0.0
    assert derivatives[1] == pytest.approx(parameters.Pm_pu / (2.0 * parameters.H_s))


def test_smib_swing_rhs_has_negative_acceleration_when_pm_is_below_pe() -> None:
    parameters = _parameters(Pm_pu=0.8, Pmax_pu=2.0, D_pu=0.0)

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=np.array([pi / 2.0, 0.0]),
        parameters=parameters,
    )

    assert derivatives[1] < 0.0


def test_smib_swing_rhs_applies_damping_against_speed_deviation() -> None:
    parameters = _parameters(H_s=5.0, D_pu=0.4, Pm_pu=1.0, Pmax_pu=2.0)
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=parameters.Pmax_pu,
    )
    omega_dev_pu = 0.02

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=np.array([delta0_rad, omega_dev_pu]),
        parameters=parameters,
    )

    expected_acceleration = -(parameters.D_pu * omega_dev_pu) / (
        2.0 * parameters.H_s
    )
    assert derivatives[1] == pytest.approx(expected_acceleration)
    assert derivatives[1] < 0.0


def test_smib_swing_rhs_uses_existing_power_angle_relation() -> None:
    parameters = _parameters(H_s=4.0, D_pu=0.0, Pm_pu=0.7, Pmax_pu=1.5)
    delta_rad = pi / 6.0
    expected_Pe_pu = electrical_power_pu(
        delta_rad=delta_rad,
        Pmax_pu=parameters.Pmax_pu,
    )

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=np.array([delta_rad, 0.0]),
        parameters=parameters,
    )

    expected_acceleration = (parameters.Pm_pu - expected_Pe_pu) / (
        2.0 * parameters.H_s
    )
    assert derivatives[1] == pytest.approx(expected_acceleration)


@pytest.mark.parametrize(
    "invalid_state",
    [
        np.array(0.0),
        np.array([0.0]),
        np.array([0.0, 0.0, 0.0]),
        np.array([[0.0, 0.0]]),
    ],
)
def test_smib_swing_rhs_rejects_invalid_state_shape(
    invalid_state: np.ndarray,
) -> None:
    with pytest.raises(ValueError, match="shape"):
        smib_swing_rhs(
            time_s=0.0,
            state=invalid_state,
            parameters=_parameters(),
        )


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf")])
def test_smib_swing_rhs_rejects_nonfinite_state_values(
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        smib_swing_rhs(
            time_s=0.0,
            state=np.array([invalid_value, 0.0]),
            parameters=_parameters(),
        )


def test_smib_swing_rhs_does_not_mutate_input_state() -> None:
    state = np.array([0.4, 0.01])
    original_state = state.copy()

    derivatives = smib_swing_rhs(
        time_s=0.0,
        state=state,
        parameters=_parameters(),
    )

    np.testing.assert_array_equal(state, original_state)
    assert not np.shares_memory(state, derivatives)
