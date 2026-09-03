import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import sincrolab.application.clearing_time as clearing_time_module
from sincrolab.analysis import (
    FirstSwingReason,
    FirstSwingStatus,
    assess_smib_first_swing,
)
from sincrolab.application import (
    SMIBClearingTimeEvaluation,
    evaluate_smib_clearing_time,
    simulate_smib_transient,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)


REFERENCE_CASE_PATH = (
    Path(__file__).parents[1]
    / "reference_cases"
    / "stable_transient_smib.json"
)


def _case_inputs() -> tuple[
    dict[str, Any],
    SMIBParameters,
    SMIBTransientNetwork,
    SMIBInitialState,
]:
    case = json.loads(REFERENCE_CASE_PATH.read_text(encoding="utf-8"))
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    return case, parameters, network, initial_state


def _evaluate(
    *,
    t_clear_s: float = 0.2,
    t_start_s: float = 0.0,
    t_end_s: float = 5.0,
    dt_s: float = 0.005,
) -> SMIBClearingTimeEvaluation:
    _, parameters, network, initial_state = _case_inputs()
    return evaluate_smib_clearing_time(
        parameters,
        initial_state,
        network,
        t_clear_s=t_clear_s,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )


def test_evaluation_preserves_effective_provenance_without_mutating_base() -> None:
    _, parameters, base_network, initial_state = _case_inputs()
    base_network_before = replace(base_network)

    evaluation = evaluate_smib_clearing_time(
        parameters,
        initial_state,
        base_network,
        t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
    )

    simulation = evaluation.simulation
    assert simulation.parameters is parameters
    assert simulation.initial_state is initial_state
    assert simulation.network is not base_network
    assert simulation.network.t_clear_s == 0.35
    assert simulation.network.Pmax_prefault_pu == base_network.Pmax_prefault_pu
    assert simulation.network.Pmax_fault_pu == base_network.Pmax_fault_pu
    assert simulation.network.Pmax_postfault_pu == base_network.Pmax_postfault_pu
    assert simulation.network.t_fault_s == base_network.t_fault_s
    assert simulation.t_start_s == 0.0
    assert simulation.t_end_s == 5.0
    assert simulation.dt_s == 0.005
    assert base_network == base_network_before
    assert base_network.t_clear_s == 0.2


def test_evaluation_matches_the_manual_time_domain_pipeline() -> None:
    _, parameters, base_network, initial_state = _case_inputs()
    effective_network = replace(base_network, t_clear_s=0.3)
    manual_simulation = simulate_smib_transient(
        parameters,
        initial_state,
        effective_network,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
    )
    manual_assessment = assess_smib_first_swing(manual_simulation)

    evaluation = evaluate_smib_clearing_time(
        parameters,
        initial_state,
        base_network,
        t_clear_s=0.3,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
    )

    assert evaluation.simulation.parameters == manual_simulation.parameters
    assert evaluation.simulation.initial_state == manual_simulation.initial_state
    assert evaluation.simulation.network == manual_simulation.network
    assert evaluation.simulation.t_start_s == manual_simulation.t_start_s
    assert evaluation.simulation.t_end_s == manual_simulation.t_end_s
    assert evaluation.simulation.dt_s == manual_simulation.dt_s
    np.testing.assert_array_equal(
        evaluation.simulation.time_s,
        manual_simulation.time_s,
    )
    np.testing.assert_array_equal(
        evaluation.simulation.delta_rad,
        manual_simulation.delta_rad,
    )
    np.testing.assert_array_equal(
        evaluation.simulation.omega_dev_pu,
        manual_simulation.omega_dev_pu,
    )
    assert evaluation.first_swing == manual_assessment


@pytest.mark.parametrize(
    (
        "t_clear_s",
        "expected_status",
        "expected_reason",
        "expected_bracket_s",
    ),
    [
        (
            0.2,
            FirstSwingStatus.STABLE,
            FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            (0.43, 0.435),
        ),
        (
            0.35,
            FirstSwingStatus.UNSTABLE,
            FirstSwingReason.CROSSING_BEFORE_REVERSAL,
            (0.495, 0.5),
        ),
    ],
    ids=["shorter_stable", "longer_unstable"],
)
def test_known_clearing_times_reproduce_reference_classifications(
    t_clear_s: float,
    expected_status: FirstSwingStatus,
    expected_reason: FirstSwingReason,
    expected_bracket_s: tuple[float, float],
) -> None:
    evaluation = _evaluate(t_clear_s=t_clear_s)

    assessment = evaluation.first_swing
    assert assessment.status is expected_status
    assert assessment.reason is expected_reason
    bracket = assessment.reversal_bracket or assessment.crossing_bracket
    assert bracket is not None
    assert bracket.left_time_s == pytest.approx(expected_bracket_s[0])
    assert bracket.right_time_s == pytest.approx(expected_bracket_s[1])


def test_evaluation_is_deterministic_and_calls_each_pipeline_stage_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    simulation_calls = 0
    assessment_calls = 0
    original_simulate = clearing_time_module.simulate_smib_transient
    original_assess = clearing_time_module.assess_smib_first_swing

    def simulate_spy(*args: object, **kwargs: object):
        nonlocal simulation_calls
        simulation_calls += 1
        return original_simulate(*args, **kwargs)

    def assess_spy(*args: object, **kwargs: object):
        nonlocal assessment_calls
        assessment_calls += 1
        return original_assess(*args, **kwargs)

    monkeypatch.setattr(
        clearing_time_module,
        "simulate_smib_transient",
        simulate_spy,
    )
    monkeypatch.setattr(
        clearing_time_module,
        "assess_smib_first_swing",
        assess_spy,
    )

    first = _evaluate(t_clear_s=0.3)
    second = _evaluate(t_clear_s=0.3)

    assert simulation_calls == 2
    assert assessment_calls == 2
    assert first.first_swing == second.first_swing
    np.testing.assert_array_equal(first.simulation.time_s, second.simulation.time_s)
    np.testing.assert_array_equal(
        first.simulation.delta_rad,
        second.simulation.delta_rad,
    )
    np.testing.assert_array_equal(
        first.simulation.omega_dev_pu,
        second.simulation.omega_dev_pu,
    )


def test_evaluation_result_is_immutable() -> None:
    evaluation = _evaluate()

    with pytest.raises(FrozenInstanceError):
        evaluation.first_swing = assess_smib_first_swing(  # type: ignore[misc]
            evaluation.simulation
        )


def test_indeterminate_first_swing_is_preserved() -> None:
    evaluation = _evaluate(t_end_s=0.3)

    assert evaluation.first_swing.status is FirstSwingStatus.INDETERMINATE
    assert evaluation.first_swing.reason is (
        FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT
    )


@pytest.mark.parametrize(
    "invalid_t_clear_s",
    [0.1, 0.05, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_clearing_time_is_rejected_by_the_network_owner(
    invalid_t_clear_s: float,
) -> None:
    with pytest.raises(ValueError, match="t_clear_s"):
        _evaluate(t_clear_s=invalid_t_clear_s)


@pytest.mark.parametrize("t_end_s", [0.2, 0.19])
def test_evaluation_requires_a_strictly_postfault_horizon(t_end_s: float) -> None:
    with pytest.raises(ValueError, match="greater than t_clear_s"):
        _evaluate(t_end_s=t_end_s)


def test_invalid_event_horizon_order_is_delegated_to_simulation() -> None:
    with pytest.raises(ValueError, match="t_start_s"):
        _evaluate(t_start_s=0.11)


@pytest.mark.parametrize(
    "invalid_dt_s",
    [0.0, -0.005, float("nan"), float("inf")],
)
def test_invalid_time_step_is_delegated_to_the_integrator(
    invalid_dt_s: float,
) -> None:
    with pytest.raises(ValueError, match="dt"):
        _evaluate(dt_s=invalid_dt_s)


def test_evaluator_has_no_equal_area_or_critical_angle_dependency() -> None:
    assert not hasattr(clearing_time_module, "assess_equal_area")
    assert not hasattr(clearing_time_module, "compute_critical_clearing_angle")
