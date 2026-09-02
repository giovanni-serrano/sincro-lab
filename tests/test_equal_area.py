from dataclasses import FrozenInstanceError
from math import asin, cos, pi

import pytest

from sincrolab.analysis import (
    DEFAULT_AREA_TOLERANCE_PU_RAD,
    EqualAreaAssessment,
    EqualAreaStatus,
    assess_equal_area,
)
from sincrolab.models import SMIBParameters, SMIBTransientNetwork


def _parameters(*, D_pu: float = 0.0, Pm_pu: float = 0.7) -> SMIBParameters:
    return SMIBParameters(
        H_s=3.5,
        D_pu=D_pu,
        f_base_hz=60.0,
        Pm_pu=Pm_pu,
    )


def _network(
    *,
    Pmax_prefault_pu: float = 1.2,
    Pmax_fault_pu: float = 0.2,
    Pmax_postfault_pu: float = 1.1,
) -> SMIBTransientNetwork:
    return SMIBTransientNetwork(
        Pmax_prefault_pu=Pmax_prefault_pu,
        Pmax_fault_pu=Pmax_fault_pu,
        Pmax_postfault_pu=Pmax_postfault_pu,
        t_fault_s=0.1,
        t_clear_s=0.2,
    )


def test_closed_form_areas_match_independent_mathematical_oracle() -> None:
    Pm_pu = 0.7
    Pmax_prefault_pu = 1.2
    Pmax_fault_pu = 0.2
    Pmax_postfault_pu = 1.1
    delta_clear_rad = 1.0
    delta_initial_rad = asin(Pm_pu / Pmax_prefault_pu)
    delta_stable_post_rad = asin(Pm_pu / Pmax_postfault_pu)
    delta_unstable_post_rad = pi - delta_stable_post_rad
    expected_fault_accelerating_area_pu_rad = (
        Pm_pu * (delta_clear_rad - delta_initial_rad)
        + Pmax_fault_pu
        * (cos(delta_clear_rad) - cos(delta_initial_rad))
    )
    expected_decelerating_area_pu_rad = (
        Pmax_postfault_pu
        * (cos(delta_clear_rad) - cos(delta_unstable_post_rad))
        - Pm_pu * (delta_unstable_post_rad - delta_clear_rad)
    )

    assessment = assess_equal_area(
        _parameters(),
        _network(),
        delta_clear_rad=delta_clear_rad,
    )

    assert assessment.delta_initial_rad == pytest.approx(delta_initial_rad)
    assert assessment.delta_stable_post_rad == pytest.approx(
        delta_stable_post_rad
    )
    assert assessment.delta_unstable_post_rad == pytest.approx(
        delta_unstable_post_rad
    )
    assert assessment.fault_accelerating_area_pu_rad == pytest.approx(
        expected_fault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.postfault_accelerating_area_pu_rad == 0.0
    assert assessment.total_accelerating_area_pu_rad == pytest.approx(
        expected_fault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.decelerating_area_available_pu_rad == pytest.approx(
        expected_decelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.area_margin_pu_rad == pytest.approx(
        expected_decelerating_area_pu_rad
        - expected_fault_accelerating_area_pu_rad,
        abs=1e-15,
    )


def test_clearing_at_initial_angle_separates_postfault_acceleration() -> None:
    parameters = _parameters()
    network = _network()
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    expected_postfault_accelerating_area_pu_rad = (
        parameters.Pm_pu * (delta_stable_post_rad - delta_initial_rad)
        + network.Pmax_postfault_pu
        * (cos(delta_stable_post_rad) - cos(delta_initial_rad))
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_initial_rad,
    )

    assert assessment.fault_accelerating_area_pu_rad == 0.0
    assert assessment.postfault_accelerating_area_pu_rad == pytest.approx(
        expected_postfault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.postfault_accelerating_area_pu_rad > 0.0
    assert assessment.total_accelerating_area_pu_rad == pytest.approx(
        expected_postfault_accelerating_area_pu_rad,
        abs=1e-15,
    )


def test_unchanged_fault_network_is_supported_only_for_zero_interval() -> None:
    parameters = _parameters()
    network = _network(Pmax_fault_pu=1.2)
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_initial_rad,
    )

    assert assessment.fault_accelerating_area_pu_rad == 0.0


def test_clearing_before_stable_postfault_equilibrium_splits_areas() -> None:
    parameters = _parameters()
    network = _network()
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    delta_clear_rad = (delta_initial_rad + delta_stable_post_rad) / 2.0
    expected_fault_accelerating_area_pu_rad = (
        parameters.Pm_pu * (delta_clear_rad - delta_initial_rad)
        + network.Pmax_fault_pu
        * (cos(delta_clear_rad) - cos(delta_initial_rad))
    )
    expected_postfault_accelerating_area_pu_rad = (
        parameters.Pm_pu * (delta_stable_post_rad - delta_clear_rad)
        + network.Pmax_postfault_pu
        * (cos(delta_stable_post_rad) - cos(delta_clear_rad))
    )
    expected_decelerating_area_pu_rad = (
        network.Pmax_postfault_pu
        * (
            cos(delta_stable_post_rad)
            - cos(delta_unstable_post_rad)
        )
        - parameters.Pm_pu
        * (delta_unstable_post_rad - delta_stable_post_rad)
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_clear_rad,
    )

    assert assessment.fault_accelerating_area_pu_rad == pytest.approx(
        expected_fault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.postfault_accelerating_area_pu_rad == pytest.approx(
        expected_postfault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.postfault_accelerating_area_pu_rad > 0.0
    assert assessment.total_accelerating_area_pu_rad == pytest.approx(
        expected_fault_accelerating_area_pu_rad
        + expected_postfault_accelerating_area_pu_rad,
        abs=1e-15,
    )
    assert assessment.decelerating_area_available_pu_rad == pytest.approx(
        expected_decelerating_area_pu_rad,
        abs=1e-15,
    )


def test_clearing_at_stable_postfault_equilibrium_has_no_postfault_acceleration(
) -> None:
    parameters = _parameters()
    network = _network()
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_stable_post_rad,
    )

    assert assessment.postfault_accelerating_area_pu_rad == 0.0
    assert (
        assessment.total_accelerating_area_pu_rad
        == assessment.fault_accelerating_area_pu_rad
    )


def test_clearing_after_stable_postfault_equilibrium_starts_deceleration_at_clear(
) -> None:
    parameters = _parameters()
    network = _network()
    delta_clear_rad = 1.0
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    expected_decelerating_area_pu_rad = (
        network.Pmax_postfault_pu
        * (cos(delta_clear_rad) - cos(delta_unstable_post_rad))
        - parameters.Pm_pu
        * (delta_unstable_post_rad - delta_clear_rad)
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_clear_rad,
    )

    assert delta_clear_rad > assessment.delta_stable_post_rad
    assert assessment.postfault_accelerating_area_pu_rad == 0.0
    assert assessment.decelerating_area_available_pu_rad == pytest.approx(
        expected_decelerating_area_pu_rad,
        abs=1e-15,
    )


def test_zero_transfer_fault_has_positive_accelerating_area() -> None:
    parameters = _parameters()
    network = _network(Pmax_fault_pu=0.0)
    delta_clear_rad = 1.0
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_clear_rad,
    )

    assert assessment.fault_accelerating_area_pu_rad == pytest.approx(
        parameters.Pm_pu * (delta_clear_rad - delta_initial_rad),
        abs=1e-15,
    )
    assert assessment.fault_accelerating_area_pu_rad > 0.0


def test_available_decelerating_area_is_positive_for_recoverable_case() -> None:
    assessment = assess_equal_area(
        _parameters(),
        _network(),
        delta_clear_rad=1.0,
    )

    assert assessment.decelerating_area_available_pu_rad > 0.0


def test_area_margin_classifies_stable_case() -> None:
    assessment = assess_equal_area(
        _parameters(),
        _network(Pmax_fault_pu=0.0),
        delta_clear_rad=1.0,
    )

    assert assessment.status is EqualAreaStatus.STABLE
    assert assessment.area_margin_pu_rad > assessment.area_tolerance_pu_rad
    assert (
        assessment.decelerating_area_available_pu_rad
        > assessment.total_accelerating_area_pu_rad
    )


def test_area_margin_classifies_unstable_case_before_unstable_equilibrium() -> None:
    assessment = assess_equal_area(
        _parameters(),
        _network(Pmax_fault_pu=0.0),
        delta_clear_rad=1.3,
    )

    assert assessment.status is EqualAreaStatus.UNSTABLE
    assert assessment.area_margin_pu_rad < -assessment.area_tolerance_pu_rad
    assert (
        assessment.total_accelerating_area_pu_rad
        > assessment.decelerating_area_available_pu_rad
    )


def test_comparison_tolerance_is_explicit_and_can_mark_area_balance() -> None:
    assessment = assess_equal_area(
        _parameters(),
        _network(Pmax_fault_pu=0.0),
        delta_clear_rad=1.0,
        area_tolerance_pu_rad=0.2,
    )

    assert assessment.status is EqualAreaStatus.AT_LIMIT
    assert assessment.area_tolerance_pu_rad == 0.2
    assert DEFAULT_AREA_TOLERANCE_PU_RAD == 1e-12


def test_assessment_is_immutable() -> None:
    assessment = assess_equal_area(
        _parameters(),
        _network(),
        delta_clear_rad=1.0,
    )

    assert isinstance(assessment, EqualAreaAssessment)
    with pytest.raises(FrozenInstanceError):
        assessment.delta_clear_rad = 1.1  # type: ignore[misc]


def test_nonzero_damping_is_rejected_as_inapplicable() -> None:
    with pytest.raises(ValueError, match=r"requires D_pu == 0"):
        assess_equal_area(
            _parameters(D_pu=0.2),
            _network(),
            delta_clear_rad=1.0,
        )


@pytest.mark.parametrize("Pm_pu", [-0.1, 0.0, 1.1, 1.2])
def test_unsupported_mechanical_power_is_rejected(Pm_pu: float) -> None:
    with pytest.raises(ValueError, match=r"0 < Pm_pu < Pmax"):
        assess_equal_area(
            _parameters(Pm_pu=Pm_pu),
            _network(),
            delta_clear_rad=1.0,
        )


@pytest.mark.parametrize("delta_clear_rad", [float("nan"), float("inf")])
def test_nonfinite_clearing_angle_is_rejected(delta_clear_rad: float) -> None:
    with pytest.raises(ValueError, match="delta_clear_rad must be finite"):
        assess_equal_area(
            _parameters(),
            _network(),
            delta_clear_rad=delta_clear_rad,
        )


def test_clearing_before_initial_angle_is_rejected() -> None:
    parameters = _parameters()
    network = _network()
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )

    with pytest.raises(ValueError, match="greater than or equal"):
        assess_equal_area(
            parameters,
            network,
            delta_clear_rad=delta_initial_rad - 0.01,
        )


def test_clearing_at_or_beyond_unstable_equilibrium_is_rejected() -> None:
    parameters = _parameters()
    network = _network()
    delta_unstable_post_rad = pi - asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )

    for delta_clear_rad in (
        delta_unstable_post_rad,
        delta_unstable_post_rad + 0.01,
    ):
        with pytest.raises(ValueError, match="less than"):
            assess_equal_area(
                parameters,
                network,
                delta_clear_rad=delta_clear_rad,
            )


def test_fault_without_forward_acceleration_is_rejected() -> None:
    with pytest.raises(ValueError, match="nonnegative accelerating power"):
        assess_equal_area(
            _parameters(),
            _network(Pmax_fault_pu=1.2),
            delta_clear_rad=1.0,
        )


def test_unfavorable_postfault_energy_balance_is_classified_not_rejected() -> None:
    parameters = _parameters()
    network = _network(Pmax_postfault_pu=0.71)
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )

    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=delta_initial_rad,
    )

    assert assessment.status is EqualAreaStatus.UNSTABLE
    assert assessment.postfault_accelerating_area_pu_rad > 0.0
    assert assessment.decelerating_area_available_pu_rad > 0.0
    assert assessment.area_margin_pu_rad < 0.0


@pytest.mark.parametrize(
    "area_tolerance_pu_rad",
    [-1.0, float("nan"), float("inf")],
)
def test_invalid_area_tolerance_is_rejected(
    area_tolerance_pu_rad: float,
) -> None:
    with pytest.raises(ValueError, match="area_tolerance_pu_rad"):
        assess_equal_area(
            _parameters(),
            _network(),
            delta_clear_rad=1.0,
            area_tolerance_pu_rad=area_tolerance_pu_rad,
        )
