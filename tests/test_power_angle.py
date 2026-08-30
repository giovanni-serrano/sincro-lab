from math import pi

import pytest

from sincrolab.models import electrical_power_pu, initial_equilibrium_angle_rad


@pytest.mark.parametrize(
    ("delta_rad", "Pmax_pu", "expected_Pe_pu"),
    [
        (0.0, 2.0, 0.0),
        (pi / 6.0, 2.0, 1.0),
        (pi / 2.0, 1.5, 1.5),
        (-pi / 2.0, 1.5, -1.5),
        (pi, 3.0, 0.0),
        (pi / 4.0, 0.0, 0.0),
    ],
)
def test_electrical_power_pu_known_values(
    delta_rad: float,
    Pmax_pu: float,
    expected_Pe_pu: float,
) -> None:
    Pe_pu = electrical_power_pu(delta_rad=delta_rad, Pmax_pu=Pmax_pu)

    assert Pe_pu == pytest.approx(expected_Pe_pu, abs=1e-12)


@pytest.mark.parametrize("invalid_Pmax_pu", [-1.0, float("nan"), float("inf")])
def test_electrical_power_pu_rejects_negative_or_nonfinite_pmax(
    invalid_Pmax_pu: float,
) -> None:
    with pytest.raises(ValueError, match="Pmax_pu"):
        electrical_power_pu(delta_rad=pi / 4.0, Pmax_pu=invalid_Pmax_pu)


@pytest.mark.parametrize(
    ("Pm_pu", "Pmax_prefault_pu", "expected_delta0_rad"),
    [
        (0.0, 2.0, 0.0),
        (1.0, 2.0, pi / 6.0),
        (2.0, 2.0, pi / 2.0),
        (-1.0, 2.0, -pi / 6.0),
        (-2.0, 2.0, -pi / 2.0),
    ],
)
def test_initial_equilibrium_angle_rad_known_values(
    Pm_pu: float,
    Pmax_prefault_pu: float,
    expected_delta0_rad: float,
) -> None:
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=Pm_pu,
        Pmax_prefault_pu=Pmax_prefault_pu,
    )

    assert delta0_rad == pytest.approx(expected_delta0_rad)


@pytest.mark.parametrize(
    "invalid_Pmax_prefault_pu",
    [0.0, -1.0, float("nan"), float("inf")],
)
def test_initial_equilibrium_angle_rad_rejects_invalid_pmax(
    invalid_Pmax_prefault_pu: float,
) -> None:
    with pytest.raises(ValueError, match="Pmax_prefault_pu"):
        initial_equilibrium_angle_rad(
            Pm_pu=0.5,
            Pmax_prefault_pu=invalid_Pmax_prefault_pu,
        )


@pytest.mark.parametrize("Pm_pu", [-1.01, 1.01, float("nan"), float("inf")])
def test_initial_equilibrium_angle_rad_rejects_values_outside_asin_domain(
    Pm_pu: float,
) -> None:
    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        initial_equilibrium_angle_rad(Pm_pu=Pm_pu, Pmax_prefault_pu=1.0)
