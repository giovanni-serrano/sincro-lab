import json
from dataclasses import FrozenInstanceError, replace
from math import asin, pi
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from sincrolab.analysis import (
    FirstSwingAssessment,
    FirstSwingReason,
    FirstSwingStatus,
    assess_smib_first_swing,
)
from sincrolab.application import (
    SMIBSimulationResult,
    simulate_smib_transient,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)


REFERENCE_CASE_PATHS = {
    "stable": Path(__file__).parents[1]
    / "reference_cases"
    / "stable_transient_smib.json",
    "near_limit": Path(__file__).parents[1]
    / "reference_cases"
    / "near_limit_transient_smib.json",
    "unstable": Path(__file__).parents[1]
    / "reference_cases"
    / "unstable_transient_smib.json",
}


def _parameters(*, Pm_pu: float = 0.7) -> SMIBParameters:
    return SMIBParameters(
        H_s=3.5,
        D_pu=0.2,
        f_base_hz=60.0,
        Pm_pu=Pm_pu,
        Pmax_pu=1.2,
    )


def _network() -> SMIBTransientNetwork:
    return SMIBTransientNetwork(
        Pmax_prefault_pu=1.2,
        Pmax_fault_pu=0.2,
        Pmax_postfault_pu=1.1,
        t_fault_s=0.1,
        t_clear_s=0.2,
    )


def _load_reference_case(case_name: str) -> dict[str, Any]:
    return json.loads(
        REFERENCE_CASE_PATHS[case_name].read_text(encoding="utf-8")
    )


def _simulate_reference_case(
    case_name: str,
) -> tuple[SMIBParameters, SMIBTransientNetwork, SMIBSimulationResult]:
    case = _load_reference_case(case_name)
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    simulation = case["simulation"]
    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=simulation["t_start_s"],
        t_end_s=simulation["t_end_s"],
        dt_s=simulation["dt_s"],
    )
    return parameters, network, result


def _no_positive_excursion_result() -> SMIBSimulationResult:
    return SMIBSimulationResult(
        time_s=np.array([0.1, 0.2, 0.3]),
        delta_rad=np.array([0.6, 0.7, 0.69]),
        omega_dev_pu=np.array([0.0, 0.0, -0.001]),
    )


@pytest.mark.parametrize(
    ("case_name", "expected_status", "expected_reason"),
    [
        (
            "stable",
            FirstSwingStatus.STABLE,
            FirstSwingReason.REVERSAL_BEFORE_CROSSING,
        ),
        (
            "near_limit",
            FirstSwingStatus.STABLE,
            FirstSwingReason.REVERSAL_BEFORE_CROSSING,
        ),
        (
            "unstable",
            FirstSwingStatus.UNSTABLE,
            FirstSwingReason.CROSSING_BEFORE_REVERSAL,
        ),
    ],
)
def test_reference_cases_receive_expected_first_swing_assessment(
    case_name: str,
    expected_status: FirstSwingStatus,
    expected_reason: FirstSwingReason,
) -> None:
    parameters, network, result = _simulate_reference_case(case_name)

    assessment = assess_smib_first_swing(result, parameters, network)

    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    assert assessment.status is expected_status
    assert assessment.reason is expected_reason
    assert assessment.delta_stable_post_rad == pytest.approx(
        delta_stable_post_rad
    )
    assert assessment.delta_unstable_post_rad == pytest.approx(
        pi - delta_stable_post_rad
    )

    if expected_status is FirstSwingStatus.STABLE:
        bracket = assessment.reversal_bracket
        assert bracket is not None
        assert assessment.crossing_bracket is None
        assert bracket.left_omega_dev_pu > 0.0
        assert bracket.right_omega_dev_pu <= 0.0
        assert np.all(
            result.delta_rad[: bracket.right_index + 1]
            < assessment.delta_unstable_post_rad
        )
    else:
        bracket = assessment.crossing_bracket
        assert bracket is not None
        assert assessment.reversal_bracket is None
        assert (
            bracket.left_delta_rad
            < assessment.delta_unstable_post_rad
            <= bracket.right_delta_rad
        )
        assert bracket.left_omega_dev_pu > 0.0
        assert bracket.right_omega_dev_pu > 0.0


def test_near_limit_reference_remains_stable_with_smaller_margin() -> None:
    assessments = {}
    results = {}
    for case_name in ("stable", "near_limit"):
        parameters, network, result = _simulate_reference_case(case_name)
        assessments[case_name] = assess_smib_first_swing(
            result,
            parameters,
            network,
        )
        results[case_name] = result

    margins = {}
    for case_name in ("stable", "near_limit"):
        assessment = assessments[case_name]
        bracket = assessment.reversal_bracket
        assert assessment.status is FirstSwingStatus.STABLE
        assert bracket is not None
        first_swing_max_rad = float(
            np.max(results[case_name].delta_rad[: bracket.right_index + 1])
        )
        margins[case_name] = (
            assessment.delta_unstable_post_rad - first_swing_max_rad
        )

    assert 0.0 < margins["near_limit"] < margins["stable"]


def test_truncated_first_swing_is_indeterminate() -> None:
    parameters, network, full_result = _simulate_reference_case("stable")
    full_assessment = assess_smib_first_swing(
        full_result,
        parameters,
        network,
    )
    reversal_bracket = full_assessment.reversal_bracket
    assert reversal_bracket is not None
    truncated_end = reversal_bracket.left_index + 1
    truncated_result = SMIBSimulationResult(
        time_s=full_result.time_s[:truncated_end],
        delta_rad=full_result.delta_rad[:truncated_end],
        omega_dev_pu=full_result.omega_dev_pu[:truncated_end],
    )

    assessment = assess_smib_first_swing(
        truncated_result,
        parameters,
        network,
    )

    assert truncated_result.omega_dev_pu[-1] > 0.0
    assert assessment.status is FirstSwingStatus.INDETERMINATE
    assert assessment.reason is FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT
    assert assessment.reversal_bracket is None
    assert assessment.crossing_bracket is None


def test_absent_positive_excursion_is_indeterminate() -> None:
    assessment = assess_smib_first_swing(
        _no_positive_excursion_result(),
        _parameters(),
        _network(),
    )

    assert assessment.status is FirstSwingStatus.INDETERMINATE
    assert assessment.reason is FirstSwingReason.NO_POSITIVE_EXCURSION
    assert assessment.reversal_bracket is None
    assert assessment.crossing_bracket is None


def test_zero_at_clearing_does_not_count_as_reversal() -> None:
    result = SMIBSimulationResult(
        time_s=np.array([0.1, 0.2, 0.3, 0.4]),
        delta_rad=np.array([0.6, 0.7, 0.8, 0.81]),
        omega_dev_pu=np.array([0.0, 0.0, 0.01, 0.0]),
    )

    assessment = assess_smib_first_swing(
        result,
        _parameters(),
        _network(),
    )

    assert assessment.status is FirstSwingStatus.STABLE
    assert assessment.reason is FirstSwingReason.REVERSAL_BEFORE_CROSSING
    bracket = assessment.reversal_bracket
    assert bracket is not None
    assert bracket.left_index == 2
    assert bracket.right_index == 3
    assert bracket.left_omega_dev_pu > 0.0
    assert bracket.right_omega_dev_pu <= 0.0


@pytest.mark.parametrize("delta_offset_rad", [0.0, 0.1], ids=["at", "beyond"])
def test_positive_excursion_at_or_beyond_unstable_equilibrium_is_ambiguous(
    delta_offset_rad: float,
) -> None:
    parameters = _parameters()
    network = _network()
    delta_unstable_post_rad = pi - asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    result = SMIBSimulationResult(
        time_s=np.array([0.1, 0.2, 0.3]),
        delta_rad=np.array(
            [
                delta_unstable_post_rad - 0.1,
                delta_unstable_post_rad + delta_offset_rad,
                delta_unstable_post_rad + delta_offset_rad + 0.1,
            ]
        ),
        omega_dev_pu=np.array([0.0, 0.01, 0.01]),
    )

    assessment = assess_smib_first_swing(result, parameters, network)

    assert assessment.status is FirstSwingStatus.INDETERMINATE
    assert assessment.reason is FirstSwingReason.EVENT_ORDER_AMBIGUOUS
    assert assessment.reversal_bracket is None
    assert assessment.crossing_bracket is None


def test_crossing_and_reversal_in_same_sample_interval_are_indeterminate() -> None:
    parameters = _parameters()
    network = _network()
    delta_unstable_post_rad = pi - asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    result = SMIBSimulationResult(
        time_s=np.array([0.1, 0.2, 0.3]),
        delta_rad=np.array(
            [
                delta_unstable_post_rad - 0.2,
                delta_unstable_post_rad - 0.1,
                delta_unstable_post_rad,
            ]
        ),
        omega_dev_pu=np.array([0.0, 0.01, 0.0]),
    )

    assessment = assess_smib_first_swing(result, parameters, network)

    assert assessment.status is FirstSwingStatus.INDETERMINATE
    assert assessment.reason is FirstSwingReason.EVENT_ORDER_AMBIGUOUS
    assert assessment.reversal_bracket is not None
    assert assessment.crossing_bracket == assessment.reversal_bracket
    assert assessment.reversal_bracket.left_index == 1
    assert assessment.reversal_bracket.right_index == 2


@pytest.mark.parametrize("Pm_pu", [-0.1, 0.0, 1.1, 1.2])
def test_assessment_rejects_unsupported_mechanical_power(Pm_pu: float) -> None:
    with pytest.raises(
        ValueError,
        match=r"0 < Pm_pu < Pmax_postfault_pu",
    ):
        assess_smib_first_swing(
            _no_positive_excursion_result(),
            _parameters(Pm_pu=Pm_pu),
            _network(),
        )


@pytest.mark.parametrize("Pmax_postfault_pu", [-0.1, 0.0, float("nan")])
def test_assessment_rejects_nonpositive_postfault_capability(
    Pmax_postfault_pu: float,
) -> None:
    invalid_network = cast(
        SMIBTransientNetwork,
        SimpleNamespace(
            Pmax_postfault_pu=Pmax_postfault_pu,
            t_clear_s=0.2,
        ),
    )

    with pytest.raises(ValueError, match="Pmax_postfault_pu"):
        assess_smib_first_swing(
            _no_positive_excursion_result(),
            _parameters(),
            invalid_network,
        )


def test_assessment_requires_the_exact_clearing_sample() -> None:
    parameters, network, result = _simulate_reference_case("stable")
    time_s = result.time_s.copy()
    clear_index = int(np.flatnonzero(time_s == network.t_clear_s)[0])
    time_s[clear_index] = np.nextafter(network.t_clear_s, float("inf"))
    shifted_result = SMIBSimulationResult(
        time_s=time_s,
        delta_rad=result.delta_rad,
        omega_dev_pu=result.omega_dev_pu,
    )

    with pytest.raises(ValueError, match="t_clear_s exactly once"):
        assess_smib_first_swing(shifted_result, parameters, network)


def test_assessment_is_immutable_and_does_not_mutate_inputs() -> None:
    parameters, network, result = _simulate_reference_case("unstable")
    parameters_before = replace(parameters)
    network_before = replace(network)
    result_before = {
        name: getattr(result, name).copy()
        for name in ("time_s", "delta_rad", "omega_dev_pu")
    }

    first_assessment = assess_smib_first_swing(result, parameters, network)
    second_assessment = assess_smib_first_swing(result, parameters, network)

    assert first_assessment == second_assessment
    assert parameters == parameters_before
    assert network == network_before
    for name, expected in result_before.items():
        values = getattr(result, name)
        np.testing.assert_array_equal(values, expected)
        assert not values.flags.writeable

    with pytest.raises(FrozenInstanceError):
        first_assessment.status = FirstSwingStatus.STABLE  # type: ignore[misc]
    bracket = first_assessment.crossing_bracket
    assert bracket is not None
    with pytest.raises(FrozenInstanceError):
        bracket.left_time_s = 0.0  # type: ignore[misc]

    assert isinstance(first_assessment, FirstSwingAssessment)
