import ast
import inspect
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

import sincrolab.application.learning as learning_module
from sincrolab.analysis import (
    CriticalClearingAngleResult,
    FirstSwingAssessment,
    FirstSwingEventBracket,
    FirstSwingReason,
    FirstSwingStatus,
)
from sincrolab.application import (
    ExplanationKind,
    PedagogicalExplanation,
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingCrossCheck,
    SMIBCriticalClearingTimeResult,
    SMIBSimulationResult,
    SMIBTransientSimulationResult,
    explain_critical_clearing_cross_check,
    explain_critical_clearing_time,
    explain_first_swing,
    explain_time_step_sensitivity,
    render_explanation_text,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
)


EVENT_BRACKET = FirstSwingEventBracket(
    left_index=10,
    right_index=11,
    left_time_s=0.5,
    right_time_s=0.51,
    left_delta_rad=1.2,
    right_delta_rad=1.21,
    left_omega_dev_pu=0.002,
    right_omega_dev_pu=0.0,
)
BASE_PARAMETERS = SMIBParameters(
    H_s=3.5,
    D_pu=0.0,
    f_base_hz=60.0,
    Pm_pu=0.7,
)
BASE_INITIAL_STATE = SMIBInitialState(
    delta_rad=0.7,
    omega_dev_pu=0.0,
)


def _first_swing(
    status: FirstSwingStatus,
    reason: FirstSwingReason,
) -> FirstSwingAssessment:
    return FirstSwingAssessment(
        status=status,
        reason=reason,
        delta_stable_post_rad=0.7,
        delta_unstable_post_rad=2.4,
        reversal_bracket=(
            EVENT_BRACKET
            if status is FirstSwingStatus.STABLE
            or reason is FirstSwingReason.EVENT_ORDER_AMBIGUOUS
            else None
        ),
        crossing_bracket=(
            replace(EVENT_BRACKET, right_omega_dev_pu=0.001)
            if status is FirstSwingStatus.UNSTABLE
            else EVENT_BRACKET
            if reason is FirstSwingReason.EVENT_ORDER_AMBIGUOUS
            else None
        ),
    )


def _evaluation(
    *,
    t_clear_s: float,
    delta_clear_rad: float,
    dt_s: float,
    status: FirstSwingStatus,
    reason: FirstSwingReason,
    parameters: SMIBParameters = BASE_PARAMETERS,
    initial_state: SMIBInitialState = BASE_INITIAL_STATE,
    Pmax_postfault_pu: float = 1.1,
    t_start_s: float = 0.0,
    t_end_s: float = 1.0,
) -> SMIBClearingTimeEvaluation:
    network = SMIBTransientNetwork(
        Pmax_prefault_pu=1.2,
        Pmax_fault_pu=0.2,
        Pmax_postfault_pu=Pmax_postfault_pu,
        t_fault_s=0.1,
        t_clear_s=t_clear_s,
    )
    trajectory = SMIBSimulationResult(
        time_s=np.array([t_start_s, 0.1, t_clear_s, t_end_s]),
        delta_rad=np.array(
            [initial_state.delta_rad, 0.75, delta_clear_rad, 1.3]
        ),
        omega_dev_pu=np.array([0.0, 0.001, 0.004, 0.0]),
    )
    return SMIBClearingTimeEvaluation(
        simulation=SMIBTransientSimulationResult(
            trajectory=trajectory,
            parameters=parameters,
            initial_state=initial_state,
            network=network,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            dt_s=dt_s,
        ),
        first_swing=_first_swing(status, reason),
    )


def _time_result(
    *,
    dt_s: float = 0.01,
    stable_t_clear_s: float = 0.30,
    unstable_t_clear_s: float = 0.31,
    parameters: SMIBParameters = BASE_PARAMETERS,
    initial_state: SMIBInitialState = BASE_INITIAL_STATE,
    Pmax_postfault_pu: float = 1.1,
    t_start_s: float = 0.0,
    t_end_s: float = 1.0,
    time_tolerance_s: float = 0.02,
    iterations: int = 4,
) -> SMIBCriticalClearingTimeResult:
    return SMIBCriticalClearingTimeResult(
        stable_evaluation=_evaluation(
            t_clear_s=stable_t_clear_s,
            delta_clear_rad=1.0,
            dt_s=dt_s,
            status=FirstSwingStatus.STABLE,
            reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            parameters=parameters,
            initial_state=initial_state,
            Pmax_postfault_pu=Pmax_postfault_pu,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
        ),
        unstable_evaluation=_evaluation(
            t_clear_s=unstable_t_clear_s,
            delta_clear_rad=1.2,
            dt_s=dt_s,
            status=FirstSwingStatus.UNSTABLE,
            reason=FirstSwingReason.CROSSING_BEFORE_REVERSAL,
            parameters=parameters,
            initial_state=initial_state,
            Pmax_postfault_pu=Pmax_postfault_pu,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
        ),
        time_tolerance_s=time_tolerance_s,
        iterations=iterations,
    )


def _cross_check(
    *,
    critical_angle_rad: float,
) -> SMIBCriticalClearingCrossCheck:
    return SMIBCriticalClearingCrossCheck(
        critical_angle_result=CriticalClearingAngleResult(
            delta_initial_rad=0.6,
            delta_stable_post_rad=0.7,
            delta_unstable_post_rad=2.4,
            critical_cosine_argument=0.4,
            delta_critical_rad=critical_angle_rad,
        ),
        clearing_time_result=_time_result(),
        angle_tolerance_rad=0.0,
    )


def _evidence(explanation: PedagogicalExplanation) -> dict[str, object]:
    return {item.key: item.value for item in explanation.evidence}


def test_stable_first_swing_explains_reversal_before_crossing() -> None:
    assessment = _first_swing(
        FirstSwingStatus.STABLE,
        FirstSwingReason.REVERSAL_BEFORE_CROSSING,
    )

    explanation = explain_first_swing(assessment)

    evidence = _evidence(explanation)
    assert explanation.kind is ExplanationKind.FIRST_SWING
    assert evidence["status"] == "stable"
    assert evidence["reason"] == "reversal_before_crossing"
    assert evidence["reversal_left_omega_dev_pu"] > 0.0
    assert evidence["reversal_right_omega_dev_pu"] <= 0.0
    assert "antes" in explanation.summary
    assert "estabilidad asintótica ni global" in " ".join(
        explanation.limitations
    )


def test_first_swing_uses_fault_acceleration_only_when_trajectory_is_supplied(
) -> None:
    evaluation = _evaluation(
        t_clear_s=0.3,
        delta_clear_rad=1.0,
        dt_s=0.01,
        status=FirstSwingStatus.STABLE,
        reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
    )

    explanation = explain_first_swing(evaluation)

    evidence = _evidence(explanation)
    assert evidence["fault_onset_omega_dev_pu"] == 0.001
    assert evidence["clearing_omega_dev_pu"] == 0.004
    assert evidence["fault_interval_speed_increased"] is True
    assert "aceleración neta del rotor" in explanation.summary


def test_unstable_first_swing_explains_crossing_with_positive_speed() -> None:
    assessment = _first_swing(
        FirstSwingStatus.UNSTABLE,
        FirstSwingReason.CROSSING_BEFORE_REVERSAL,
    )

    explanation = explain_first_swing(assessment)

    evidence = _evidence(explanation)
    assert evidence["status"] == "unstable"
    assert evidence["reason"] == "crossing_before_reversal"
    assert evidence["crossing_left_omega_dev_pu"] > 0.0
    assert evidence["crossing_right_omega_dev_pu"] > 0.0
    assert "antes de una reversión" in explanation.summary
    assert "multimáquina" in " ".join(explanation.limitations)


@pytest.mark.parametrize(
    "reason",
    [
        FirstSwingReason.NO_POSITIVE_EXCURSION,
        FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT,
    ],
)
def test_indeterminate_first_swing_is_never_reclassified(
    reason: FirstSwingReason,
) -> None:
    assessment = _first_swing(FirstSwingStatus.INDETERMINATE, reason)

    explanation = explain_first_swing(assessment)

    evidence = _evidence(explanation)
    assert evidence["status"] == "indeterminate"
    assert evidence["reason"] == reason.value
    assert "sigue siendo no concluyente" in explanation.summary
    assert "clasificó como estable" not in explanation.summary
    assert "clasificó como inestable" not in explanation.summary


def test_event_order_ambiguous_without_brackets_preserves_absent_evidence(
) -> None:
    assessment = replace(
        _first_swing(
            FirstSwingStatus.INDETERMINATE,
            FirstSwingReason.NO_POSITIVE_EXCURSION,
        ),
        reason=FirstSwingReason.EVENT_ORDER_AMBIGUOUS,
    )

    explanation = explain_first_swing(assessment)

    evidence = _evidence(explanation)
    assert evidence["status"] == "indeterminate"
    assert evidence["reason"] == "event_order_ambiguous"
    assert not any(key.startswith("ambiguous_event_") for key in evidence)
    assert "ambiguous_events_share_sampled_bracket" not in evidence
    assert "orden continuo" not in explanation.summary


def test_event_order_ambiguous_preserves_both_events_in_one_bracket() -> None:
    assessment = _first_swing(
        FirstSwingStatus.INDETERMINATE,
        FirstSwingReason.EVENT_ORDER_AMBIGUOUS,
    )

    explanation = explain_first_swing(assessment)

    evidence = _evidence(explanation)
    assert evidence["reversal_observed_in_ambiguous_bracket"] is True
    assert evidence["crossing_observed_in_ambiguous_bracket"] is True
    assert evidence["ambiguous_events_share_sampled_bracket"] is True
    assert evidence["ambiguous_event_left_index"] == EVENT_BRACKET.left_index
    assert evidence["ambiguous_event_right_index"] == EVENT_BRACKET.right_index
    assert "reversal_left_time_s" not in evidence
    assert "crossing_left_time_s" not in evidence
    assert "mismo par de muestras adyacentes" in explanation.summary
    assert "orden continuo no está resuelto" in explanation.summary


def test_first_swing_explanation_is_immutable_and_deterministic() -> None:
    assessment = _first_swing(
        FirstSwingStatus.STABLE,
        FirstSwingReason.REVERSAL_BEFORE_CROSSING,
    )

    first = explain_first_swing(assessment)
    second = explain_first_swing(assessment)

    assert first == second
    assert render_explanation_text(first) == render_explanation_text(second)
    assert isinstance(first.evidence, tuple)
    assert isinstance(first.limitations, tuple)
    with pytest.raises(FrozenInstanceError):
        first.summary = "changed"  # type: ignore[misc]


def test_h19_explanation_preserves_endpoints_without_a_cct_value() -> None:
    result = _time_result()

    explanation = explain_critical_clearing_time(result)

    evidence = _evidence(explanation)
    assert evidence["stable_t_clear_s"] == result.stable_t_clear_s
    assert evidence["unstable_t_clear_s"] == result.unstable_t_clear_s
    assert evidence["bracket_width_s"] == result.bracket_width_s
    assert "cct_estimate_s" not in evidence
    rendered = render_explanation_text(explanation).lower()
    assert "cct exacto" not in rendered
    assert "±" not in rendered


def test_h19_time_tolerance_is_only_a_search_stopping_criterion() -> None:
    explanation = explain_critical_clearing_time(_time_result())

    tolerance = next(
        item
        for item in explanation.evidence
        if item.key == "time_tolerance_s"
    )
    limitations = " ".join(explanation.limitations)
    assert tolerance.statement == "Criterio de parada utilizado por la búsqueda por bisección."
    assert "no incertidumbre física" in limitations
    assert "no" in limitations
    assert "estimación del error de integración" in limitations
    assert "convergencia respecto al paso temporal" in limitations


def test_h20_consistent_explanation_keeps_analytic_and_temporal_routes() -> None:
    result = _cross_check(critical_angle_rad=1.1)

    explanation = explain_critical_clearing_cross_check(result)

    evidence = _evidence(explanation)
    assert evidence["analytic_critical_angle_rad"] == 1.1
    assert evidence["temporal_stable_clearing_angle_rad"] == 1.0
    assert evidence["temporal_unstable_clearing_angle_rad"] == 1.2
    assert evidence["is_consistent"] is True
    assert "ángulo crítico analítico" in explanation.summary
    assert "intervalo estable/inestable" in explanation.summary
    assert "aumenta la confianza" in " ".join(explanation.limitations)
    assert "no son oráculos analíticos" in " ".join(explanation.limitations)


def test_h20_inconsistent_explanation_does_not_hide_disagreement() -> None:
    result = _cross_check(critical_angle_rad=0.8)

    explanation = explain_critical_clearing_cross_check(result)

    assert _evidence(explanation)["is_consistent"] is False
    assert "no es consistente" in explanation.summary
    assert "aumenta la confianza" not in explanation.summary


def test_comparable_h19_results_allow_time_step_explanation() -> None:
    coarse = _time_result(
        dt_s=0.1,
        stable_t_clear_s=0.27,
        unstable_t_clear_s=0.28,
    )
    fine = _time_result(
        dt_s=0.025,
        stable_t_clear_s=0.30,
        unstable_t_clear_s=0.31,
    )

    explanation = explain_time_step_sensitivity((fine, coarse))

    evidence = _evidence(explanation)
    assert evidence["run_1_dt_s"] == 0.1
    assert evidence["run_2_dt_s"] == 0.025
    assert evidence["brackets_differ"] is True
    assert explanation.summary.startswith(
        "Entre los resultados suministrados con procedencia conservada coincidente y distintos pasos temporales, los intervalos de extremos difieren."
    )
    limitations = " ".join(explanation.limitations)
    assert "no implica que el efecto del paso temporal sea igualmente pequeño" in limitations
    assert "intervalos de extremos con distintos pasos" in limitations
    assert "son compatibles con sensibilidad a la resolución temporal" in limitations
    assert "no demuestran un defecto del software" in limitations
    assert "no conservan el intervalo inicial de búsqueda ni el límite de iteraciones" in limitations
    assert "no permiten establecer" in limitations
    assert "el paso temporal fuera la única entrada de búsqueda diferente" in limitations
    assert "no realiza un estudio de convergencia" in limitations
    assert "clasificación" not in render_explanation_text(explanation).lower()


def test_time_step_explanation_rejects_different_physical_parameters() -> None:
    baseline = _time_result(dt_s=0.1)
    different_machine = _time_result(
        dt_s=0.025,
        parameters=replace(BASE_PARAMETERS, H_s=4.0),
    )

    with pytest.raises(
        ValueError,
        match="matching physical, simulation, and search provenance",
    ):
        explain_time_step_sensitivity((baseline, different_machine))


def test_time_step_explanation_rejects_different_network_physics() -> None:
    baseline = _time_result(dt_s=0.1)
    different_network = _time_result(
        dt_s=0.025,
        Pmax_postfault_pu=1.05,
    )

    with pytest.raises(
        ValueError,
        match="matching physical, simulation, and search provenance",
    ):
        explain_time_step_sensitivity((baseline, different_network))


def test_time_step_explanation_rejects_different_simulation_horizon() -> None:
    baseline = _time_result(dt_s=0.1)
    different_horizon = _time_result(dt_s=0.025, t_end_s=1.2)

    with pytest.raises(
        ValueError,
        match="matching physical, simulation, and search provenance",
    ):
        explain_time_step_sensitivity((baseline, different_horizon))


@pytest.mark.parametrize(
    "changed_search",
    [
        {"time_tolerance_s": 0.01},
        {"iterations": 5},
    ],
    ids=["time_tolerance", "iterations"],
)
def test_time_step_explanation_rejects_different_h19_search_provenance(
    changed_search: dict[str, float | int],
) -> None:
    baseline = _time_result(dt_s=0.1)
    different_search = _time_result(dt_s=0.025, **changed_search)

    with pytest.raises(
        ValueError,
        match="matching physical, simulation, and search provenance",
    ):
        explain_time_step_sensitivity((baseline, different_search))


def test_equivalent_time_step_inputs_have_order_independent_output() -> None:
    coarse = _time_result(dt_s=0.1)
    fine = _time_result(dt_s=0.025)

    forward = explain_time_step_sensitivity((coarse, fine))
    reverse = explain_time_step_sensitivity((fine, coarse))

    assert forward == reverse
    assert render_explanation_text(forward) == render_explanation_text(reverse)
    assert forward.summary.startswith(
        "Entre los resultados suministrados con procedencia conservada coincidente y distintos pasos temporales, los intervalos de extremos son iguales en los valores numéricos reportados."
    )


def test_explanations_contain_no_generated_identity_or_timestamp_fields() -> None:
    explanations = (
        explain_first_swing(
            _first_swing(
                FirstSwingStatus.STABLE,
                FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            )
        ),
        explain_critical_clearing_time(_time_result()),
        explain_critical_clearing_cross_check(
            _cross_check(critical_angle_rad=1.1)
        ),
    )

    for explanation in explanations:
        keys = {item.key for item in explanation.evidence}
        assert "timestamp" not in keys
        assert "uuid" not in keys
        assert "id" not in keys


def test_learning_module_has_no_solver_scipy_or_ui_dependencies() -> None:
    tree = ast.parse(inspect.getsource(learning_module))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    source = inspect.getsource(learning_module)

    assert imported_modules <= {
        "__future__",
        "collections.abc",
        "dataclasses",
        "enum",
        "sincrolab.analysis",
        "sincrolab.application.clearing_time",
        "sincrolab.application.critical_clearing_cross_check",
        "sincrolab.simulation",
    }
    for forbidden in (
        "scipy",
        "PySide6",
        "simulate_smib",
        "assess_smib",
        "compute_critical",
        "electrical_power_pu",
    ):
        assert forbidden not in source
