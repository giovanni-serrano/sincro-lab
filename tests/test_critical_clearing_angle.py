from dataclasses import FrozenInstanceError
from math import acos, asin, cos, inf, nextafter, pi

import pytest

from sincrolab.analysis import (
    CriticalClearingAngleResult,
    EqualAreaStatus,
    assess_equal_area,
    compute_critical_clearing_angle,
)
from sincrolab.analysis.equal_area import _validated_acos_argument
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


def test_critical_angle_matches_independent_closed_form_oracle() -> None:
    Pm_pu = 0.7
    Pmax_prefault_pu = 1.2
    Pmax_fault_pu = 0.2
    Pmax_postfault_pu = 1.1
    delta_initial_rad = asin(Pm_pu / Pmax_prefault_pu)
    delta_stable_post_rad = asin(Pm_pu / Pmax_postfault_pu)
    delta_unstable_post_rad = pi - delta_stable_post_rad
    expected_cosine_argument = (
        Pmax_postfault_pu * cos(delta_unstable_post_rad)
        + Pm_pu * (delta_unstable_post_rad - delta_initial_rad)
        - Pmax_fault_pu * cos(delta_initial_rad)
    ) / (Pmax_postfault_pu - Pmax_fault_pu)
    expected_delta_critical_rad = acos(expected_cosine_argument)

    result = compute_critical_clearing_angle(_parameters(), _network())

    assert result.delta_initial_rad == pytest.approx(delta_initial_rad)
    assert result.delta_stable_post_rad == pytest.approx(
        delta_stable_post_rad
    )
    assert result.delta_unstable_post_rad == pytest.approx(
        delta_unstable_post_rad
    )
    assert result.critical_cosine_argument == pytest.approx(
        expected_cosine_argument,
        abs=1e-15,
    )
    assert result.delta_critical_rad == pytest.approx(
        expected_delta_critical_rad,
        abs=1e-15,
    )


def test_equal_area_balance_changes_sign_around_critical_angle() -> None:
    parameters = _parameters()
    network = _network()
    result = compute_critical_clearing_angle(parameters, network)
    epsilon_angle_rad = 1e-4

    before = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=result.delta_critical_rad - epsilon_angle_rad,
    )
    at_limit = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=result.delta_critical_rad,
    )
    after = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=result.delta_critical_rad + epsilon_angle_rad,
    )

    assert before.status is EqualAreaStatus.STABLE
    assert before.area_margin_pu_rad > 0.0
    assert at_limit.status is EqualAreaStatus.AT_LIMIT
    assert at_limit.area_margin_pu_rad == pytest.approx(0.0, abs=1e-12)
    assert after.status is EqualAreaStatus.UNSTABLE
    assert after.area_margin_pu_rad < 0.0


def test_closed_form_also_supports_critical_angle_before_stable_equilibrium(
) -> None:
    parameters = _parameters()
    network = _network(Pmax_fault_pu=0.0, Pmax_postfault_pu=0.8)

    result = compute_critical_clearing_angle(parameters, network)
    assessment = assess_equal_area(
        parameters,
        network,
        delta_clear_rad=result.delta_critical_rad,
    )

    assert result.delta_initial_rad < result.delta_critical_rad
    assert result.delta_critical_rad < result.delta_stable_post_rad
    assert assessment.postfault_accelerating_area_pu_rad > 0.0
    assert assessment.status is EqualAreaStatus.AT_LIMIT


def test_zero_transfer_fault_has_closed_form_critical_angle() -> None:
    parameters = _parameters()
    network = _network(Pmax_fault_pu=0.0)
    delta_initial_rad = asin(
        parameters.Pm_pu / network.Pmax_prefault_pu
    )
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    expected_argument = (
        network.Pmax_postfault_pu * cos(delta_unstable_post_rad)
        + parameters.Pm_pu
        * (delta_unstable_post_rad - delta_initial_rad)
    ) / network.Pmax_postfault_pu

    result = compute_critical_clearing_angle(parameters, network)

    assert result.critical_cosine_argument == pytest.approx(
        expected_argument,
        abs=1e-15,
    )
    assert result.delta_critical_rad == pytest.approx(
        acos(expected_argument),
        abs=1e-15,
    )


def test_nonzero_damping_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"requires D_pu == 0"):
        compute_critical_clearing_angle(
            _parameters(D_pu=0.2),
            _network(),
        )


@pytest.mark.parametrize("Pm_pu", [-0.1, 0.0, 1.2])
def test_invalid_prefault_regime_is_rejected(Pm_pu: float) -> None:
    with pytest.raises(ValueError, match="Pmax_prefault_pu"):
        compute_critical_clearing_angle(
            _parameters(Pm_pu=Pm_pu),
            _network(),
        )


def test_postfault_regime_without_equilibrium_is_rejected() -> None:
    with pytest.raises(ValueError, match="Pmax_postfault_pu"):
        compute_critical_clearing_angle(
            _parameters(Pm_pu=1.1),
            _network(),
        )


def test_fault_without_forward_acceleration_is_rejected() -> None:
    with pytest.raises(ValueError, match="Pmax_fault_pu < Pmax_prefault_pu"):
        compute_critical_clearing_angle(
            _parameters(),
            _network(Pmax_fault_pu=1.2),
        )


def test_identical_fault_and_postfault_curves_are_rejected() -> None:
    with pytest.raises(ValueError, match="distinct fault and postfault"):
        compute_critical_clearing_angle(
            _parameters(),
            _network(Pmax_fault_pu=0.8, Pmax_postfault_pu=0.8),
        )


def test_materially_invalid_acos_argument_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        compute_critical_clearing_angle(
            _parameters(),
            _network(Pmax_fault_pu=0.6, Pmax_postfault_pu=0.75),
        )


def test_acos_domain_adjustment_is_limited_to_a_few_ulps() -> None:
    assert _validated_acos_argument(nextafter(1.0, inf)) == 1.0
    assert _validated_acos_argument(nextafter(-1.0, -inf)) == -1.0
    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        _validated_acos_argument(1.01)


def test_result_is_deterministic_and_immutable() -> None:
    first = compute_critical_clearing_angle(_parameters(), _network())
    second = compute_critical_clearing_angle(_parameters(), _network())

    assert first == second
    assert isinstance(first, CriticalClearingAngleResult)
    with pytest.raises(FrozenInstanceError):
        first.delta_critical_rad = 1.0  # type: ignore[misc]
