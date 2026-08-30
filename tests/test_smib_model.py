from dataclasses import FrozenInstanceError, fields

import pytest

from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    electrical_power_pu,
    initial_equilibrium_angle_rad,
)


def _valid_parameters(**overrides: float) -> SMIBParameters:
    values = {
        "H_s": 3.5,
        "D_pu": 0.1,
        "f_base_hz": 60.0,
        "Pm_pu": 0.8,
        "Pmax_pu": 2.0,
    }
    values.update(overrides)
    return SMIBParameters(**values)


def test_smib_domain_values_have_explicit_fields_and_units() -> None:
    parameters = _valid_parameters()
    initial_state = SMIBInitialState(delta_rad=0.4, omega_dev_pu=0.0)

    assert tuple(field.name for field in fields(parameters)) == (
        "H_s",
        "D_pu",
        "f_base_hz",
        "Pm_pu",
        "Pmax_pu",
    )
    assert tuple(field.name for field in fields(initial_state)) == (
        "delta_rad",
        "omega_dev_pu",
    )


def test_smib_domain_values_reuse_existing_power_angle_relations() -> None:
    parameters = _valid_parameters(Pm_pu=1.0, Pmax_pu=2.0)
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=parameters.Pmax_pu,
    )
    initial_state = SMIBInitialState(delta_rad=delta0_rad, omega_dev_pu=0.0)

    Pe_pu = electrical_power_pu(
        delta_rad=initial_state.delta_rad,
        Pmax_pu=parameters.Pmax_pu,
    )

    assert Pe_pu == pytest.approx(parameters.Pm_pu)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("H_s", 0.0),
        ("H_s", -1.0),
        ("H_s", float("nan")),
        ("H_s", float("inf")),
        ("f_base_hz", 0.0),
        ("f_base_hz", -50.0),
        ("f_base_hz", float("nan")),
        ("f_base_hz", float("inf")),
        ("Pmax_pu", -1.0),
        ("Pmax_pu", float("nan")),
        ("Pmax_pu", float("inf")),
        ("D_pu", float("nan")),
        ("D_pu", float("inf")),
        ("Pm_pu", float("nan")),
        ("Pm_pu", float("inf")),
    ],
)
def test_smib_parameters_reject_unequivocally_invalid_values(
    field_name: str,
    invalid_value: float,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        _valid_parameters(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("delta_rad", float("nan")),
        ("delta_rad", float("inf")),
        ("omega_dev_pu", float("nan")),
        ("omega_dev_pu", float("inf")),
    ],
)
def test_smib_initial_state_rejects_nonfinite_values(
    field_name: str,
    invalid_value: float,
) -> None:
    values = {"delta_rad": 0.4, "omega_dev_pu": 0.0}
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        SMIBInitialState(**values)


def test_smib_parameters_accept_zero_transfer_capability() -> None:
    parameters = _valid_parameters(Pmax_pu=0.0)

    assert parameters.Pmax_pu == 0.0


def test_smib_domain_values_do_not_impose_equilibrium_or_sign_assumptions() -> None:
    parameters = _valid_parameters(D_pu=-0.1, Pm_pu=1.2, Pmax_pu=1.0)
    initial_state = SMIBInitialState(delta_rad=-4.0, omega_dev_pu=-0.01)

    assert parameters.D_pu == -0.1
    assert parameters.Pm_pu > parameters.Pmax_pu
    assert initial_state.delta_rad == -4.0
    assert initial_state.omega_dev_pu == -0.01


def test_smib_domain_values_are_immutable() -> None:
    parameters = _valid_parameters()
    initial_state = SMIBInitialState(delta_rad=0.4, omega_dev_pu=0.0)

    with pytest.raises(FrozenInstanceError):
        setattr(parameters, "H_s", 4.0)
    with pytest.raises(FrozenInstanceError):
        setattr(initial_state, "delta_rad", 0.5)
