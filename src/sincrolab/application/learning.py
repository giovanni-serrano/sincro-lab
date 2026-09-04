"""Deterministic pedagogical interpretations of scientific results."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from sincrolab.analysis import (
    FirstSwingAssessment,
    FirstSwingEventBracket,
    FirstSwingReason,
    FirstSwingStatus,
)
from sincrolab.application.clearing_time import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
)
from sincrolab.application.critical_clearing_cross_check import (
    SMIBCriticalClearingCrossCheck,
)
from sincrolab.simulation import SMIBTransientSimulationResult


EvidenceValue = bool | float | int | str


class ExplanationKind(Enum):
    """Scientific result family interpreted by an explanation."""

    FIRST_SWING = "first_swing"
    CRITICAL_CLEARING_TIME = "critical_clearing_time"
    CRITICAL_CLEARING_CROSS_CHECK = "critical_clearing_cross_check"
    TIME_STEP_SENSITIVITY = "time_step_sensitivity"


class LearningConcept(Enum):
    """Stable identifiers for concepts that an interface may emphasize."""

    ROTOR_ANGLE = "rotor_angle"
    SPEED_DEVIATION = "speed_deviation"
    FIRST_SWING = "first_swing"
    UNSTABLE_EQUILIBRIUM = "unstable_equilibrium"
    CLEARING_TIME = "clearing_time"
    EQUAL_AREA = "equal_area"
    TIME_STEP = "time_step"


@dataclass(frozen=True)
class ExplanationEvidence:
    """One ordered, machine-readable fact and its pedagogical meaning."""

    key: str
    value: EvidenceValue
    statement: str
    unit: str | None = None


@dataclass(frozen=True)
class PedagogicalExplanation:
    """Immutable interpretation subordinate to an existing scientific result."""

    kind: ExplanationKind
    title: str
    summary: str
    evidence: tuple[ExplanationEvidence, ...]
    limitations: tuple[str, ...]
    concepts: tuple[LearningConcept, ...]


def explain_first_swing(
    result: FirstSwingAssessment | SMIBClearingTimeEvaluation,
) -> PedagogicalExplanation:
    """Explain a sampled first-swing result without reclassifying it."""
    if isinstance(result, FirstSwingAssessment):
        assessment = result
        evaluation = None
    else:
        assessment = result.first_swing
        evaluation = result
    supported_pairs = {
        (FirstSwingStatus.STABLE, FirstSwingReason.REVERSAL_BEFORE_CROSSING),
        (FirstSwingStatus.UNSTABLE, FirstSwingReason.CROSSING_BEFORE_REVERSAL),
        (FirstSwingStatus.INDETERMINATE, FirstSwingReason.NO_POSITIVE_EXCURSION),
        (
            FirstSwingStatus.INDETERMINATE,
            FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT,
        ),
        (FirstSwingStatus.INDETERMINATE, FirstSwingReason.EVENT_ORDER_AMBIGUOUS),
    }
    if (assessment.status, assessment.reason) not in supported_pairs:
        raise ValueError(
            "first-swing status and reason do not match the H15 contract"
        )

    evidence = [
        ExplanationEvidence(
            key="status",
            value=assessment.status.value,
            statement="H15 sampled first-swing status.",
        ),
        ExplanationEvidence(
            key="reason",
            value=assessment.reason.value,
            statement="H15 reason that produced the status.",
        ),
        ExplanationEvidence(
            key="delta_stable_post_rad",
            value=assessment.delta_stable_post_rad,
            unit="rad",
            statement="Relevant stable postfault equilibrium angle.",
        ),
        ExplanationEvidence(
            key="delta_unstable_post_rad",
            value=assessment.delta_unstable_post_rad,
            unit="rad",
            statement="Relevant unstable postfault equilibrium angle.",
        ),
    ]
    fault_clause = ""
    if evaluation is not None:
        fault_evidence, fault_clause = _fault_interval_evidence(evaluation)
        evidence.extend(fault_evidence)
    if assessment.status is FirstSwingStatus.STABLE:
        bracket = _required_bracket(
            assessment.reversal_bracket,
            "STABLE assessment requires a reversal bracket",
        )
        evidence.extend(_event_bracket_evidence("reversal", bracket))
        summary = (
            "The sampled classical SMIB trajectory was classified STABLE for "
            "the first swing. A positive-speed forward excursion was followed "
            "by a sampled rotor-speed reversal before the relevant unstable "
            "postfault equilibrium was crossed."
            + fault_clause
        )
    elif assessment.status is FirstSwingStatus.UNSTABLE:
        bracket = _required_bracket(
            assessment.crossing_bracket,
            "UNSTABLE assessment requires a crossing bracket",
        )
        evidence.extend(_event_bracket_evidence("crossing", bracket))
        summary = (
            "The sampled classical SMIB trajectory was classified UNSTABLE for "
            "the first swing. It reached the relevant unstable postfault "
            "equilibrium before a rotor-speed reversal, with positive speed "
            "at both samples of the crossing bracket."
            + fault_clause
        )
    else:
        summary = _indeterminate_summary(assessment.reason) + fault_clause
        if assessment.reason is FirstSwingReason.EVENT_ORDER_AMBIGUOUS:
            reversal_bracket = assessment.reversal_bracket
            crossing_bracket = assessment.crossing_bracket
            if reversal_bracket is None and crossing_bracket is None:
                pass
            elif (
                reversal_bracket is None
                or crossing_bracket is None
                or reversal_bracket != crossing_bracket
            ):
                raise ValueError(
                    "ambiguous H15 events must share one sampled bracket"
                )
            else:
                summary += (
                    " Reversal and unstable-equilibrium crossing were both "
                    "observed in the same adjacent-sample bracket, so their "
                    "continuous order is unresolved."
                )
                evidence.extend(
                    _event_bracket_evidence(
                        "ambiguous_event",
                        reversal_bracket,
                    )
                )
                evidence.extend(
                    (
                        ExplanationEvidence(
                            key="reversal_observed_in_ambiguous_bracket",
                            value=True,
                            statement=(
                                "Rotor-speed reversal was observed in the "
                                "ambiguous sampled bracket."
                            ),
                        ),
                        ExplanationEvidence(
                            key="crossing_observed_in_ambiguous_bracket",
                            value=True,
                            statement=(
                                "Unstable-equilibrium crossing was observed "
                                "in the ambiguous sampled bracket."
                            ),
                        ),
                        ExplanationEvidence(
                            key="ambiguous_events_share_sampled_bracket",
                            value=True,
                            statement=(
                                "Both candidate events share the same pair "
                                "of adjacent samples."
                            ),
                        ),
                    )
                )
        elif assessment.reversal_bracket is not None:
            evidence.extend(
                _event_bracket_evidence(
                    "event_order_candidate",
                    assessment.reversal_bracket,
                )
            )

    return PedagogicalExplanation(
        kind=ExplanationKind.FIRST_SWING,
        title="Sampled first-swing assessment",
        summary=summary,
        evidence=tuple(evidence),
        limitations=(
            "The status applies only to the sampled forward first swing; it "
            "does not establish asymptotic or global stability.",
            "Event brackets contain adjacent trajectory samples; they are not "
            "interpolated continuous-event times.",
            "The interpretation is for the classical SMIB model and is not a "
            "general multimachine-system conclusion.",
        ),
        concepts=(
            LearningConcept.ROTOR_ANGLE,
            LearningConcept.SPEED_DEVIATION,
            LearningConcept.FIRST_SWING,
            LearningConcept.UNSTABLE_EQUILIBRIUM,
        ),
    )


def explain_critical_clearing_time(
    result: SMIBCriticalClearingTimeResult,
) -> PedagogicalExplanation:
    """Explain H19's stable-to-unstable temporal bracket as a bracket."""
    evidence = (
        ExplanationEvidence(
            key="stable_t_clear_s",
            value=result.stable_t_clear_s,
            unit="s",
            statement="Lower endpoint classified STABLE by H15.",
        ),
        ExplanationEvidence(
            key="stable_status",
            value=result.stable_evaluation.first_swing.status.value,
            statement="First-swing status at the lower endpoint.",
        ),
        ExplanationEvidence(
            key="stable_reason",
            value=result.stable_evaluation.first_swing.reason.value,
            statement="H15 reason at the lower endpoint.",
        ),
        ExplanationEvidence(
            key="unstable_t_clear_s",
            value=result.unstable_t_clear_s,
            unit="s",
            statement="Upper endpoint classified UNSTABLE by H15.",
        ),
        ExplanationEvidence(
            key="unstable_status",
            value=result.unstable_evaluation.first_swing.status.value,
            statement="First-swing status at the upper endpoint.",
        ),
        ExplanationEvidence(
            key="unstable_reason",
            value=result.unstable_evaluation.first_swing.reason.value,
            statement="H15 reason at the upper endpoint.",
        ),
        ExplanationEvidence(
            key="bracket_width_s",
            value=result.bracket_width_s,
            unit="s",
            statement="Width of the final stable-to-unstable time bracket.",
        ),
        ExplanationEvidence(
            key="time_tolerance_s",
            value=result.time_tolerance_s,
            unit="s",
            statement="Stopping criterion used by the bisection search.",
        ),
        ExplanationEvidence(
            key="iterations",
            value=result.iterations,
            statement="Number of midpoint evaluations performed by H19.",
        ),
        ExplanationEvidence(
            key="dt_s",
            value=_result_dt_s(result),
            unit="s",
            statement="Time step used by both endpoint simulations.",
        ),
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.CRITICAL_CLEARING_TIME,
        title="Critical-clearing transition bracket",
        summary=(
            "With the supplied numerical configuration, H19 found a STABLE "
            "first-swing result at the lower clearing-time endpoint and an "
            "UNSTABLE result at the upper endpoint. The transition is bounded "
            "between those evaluated times under the search procedure used."
        ),
        evidence=evidence,
        limitations=(
            "time_tolerance_s is a bisection stopping criterion, not physical "
            "uncertainty or an integration-error estimate.",
            "The bracket midpoint is only a numerical summary of the bracket "
            "and must not be presented as the critical clearing time.",
            "A narrow bracket does not establish convergence with respect to "
            "dt_s.",
        ),
        concepts=(
            LearningConcept.CLEARING_TIME,
            LearningConcept.FIRST_SWING,
            LearningConcept.TIME_STEP,
        ),
    )


def explain_critical_clearing_cross_check(
    result: SMIBCriticalClearingCrossCheck,
) -> PedagogicalExplanation:
    """Explain H20's comparison without merging its two scientific routes."""
    consistency_statement = (
        "The analytic critical angle is consistent with the temporal endpoint "
        "angles under the stated angular comparison tolerance."
        if result.is_consistent
        else "The analytic critical angle is not consistent with the temporal "
        "endpoint angles under the stated angular comparison tolerance."
    )
    evidence = (
        ExplanationEvidence(
            key="analytic_critical_angle_rad",
            value=result.critical_angle_rad,
            unit="rad",
            statement="H17 equal-area critical angle from the analytic route.",
        ),
        ExplanationEvidence(
            key="temporal_stable_t_clear_s",
            value=result.clearing_time_result.stable_t_clear_s,
            unit="s",
            statement="H19 temporal bracket's STABLE endpoint time.",
        ),
        ExplanationEvidence(
            key="temporal_unstable_t_clear_s",
            value=result.clearing_time_result.unstable_t_clear_s,
            unit="s",
            statement="H19 temporal bracket's UNSTABLE endpoint time.",
        ),
        ExplanationEvidence(
            key="temporal_stable_clearing_angle_rad",
            value=result.stable_clearing_angle_rad,
            unit="rad",
            statement="Clearing angle sampled by the stable endpoint trajectory.",
        ),
        ExplanationEvidence(
            key="temporal_unstable_clearing_angle_rad",
            value=result.unstable_clearing_angle_rad,
            unit="rad",
            statement=(
                "Clearing angle sampled by the unstable endpoint trajectory."
            ),
        ),
        ExplanationEvidence(
            key="stable_angle_gap_rad",
            value=result.stable_angle_gap_rad,
            unit="rad",
            statement=(
                "Analytic angle minus the stable endpoint clearing angle."
            ),
        ),
        ExplanationEvidence(
            key="unstable_angle_gap_rad",
            value=result.unstable_angle_gap_rad,
            unit="rad",
            statement=(
                "Unstable endpoint clearing angle minus the analytic angle."
            ),
        ),
        ExplanationEvidence(
            key="temporal_angle_bracket_width_rad",
            value=result.clearing_angle_bracket_width_rad,
            unit="rad",
            statement="Width between temporal endpoint clearing angles.",
        ),
        ExplanationEvidence(
            key="is_consistent",
            value=result.is_consistent,
            statement=consistency_statement,
        ),
        ExplanationEvidence(
            key="angle_tolerance_rad",
            value=result.angle_tolerance_rad,
            unit="rad",
            statement="Angular allowance used only for the H20 comparison.",
        ),
    )
    summary = (
        "H20 kept two routes separate: H17 produced an analytic equal-area "
        "critical angle, while H19 produced a stable-to-unstable temporal "
        "bracket whose endpoint trajectories supplied clearing angles. "
        + consistency_statement
    )
    confidence_limitation = (
        "Observed agreement increases confidence in this configured case; it "
        "does not establish universal model validity."
        if result.is_consistent
        else "The disagreement remains visible for investigation; H24 does "
        "not reconcile or override either scientific route."
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.CRITICAL_CLEARING_CROSS_CHECK,
        title="Equal-area and temporal cross-check",
        summary=summary,
        evidence=evidence,
        limitations=(
            "The comparison applies to the compatible classical zero-damping "
            "equal-area case.",
            "The analytic route did not set or alter the temporal search "
            "endpoints.",
            "The temporal endpoints remain RK4 trajectory evidence and are "
            "not analytic oracles.",
            confidence_limitation,
        ),
        concepts=(
            LearningConcept.EQUAL_AREA,
            LearningConcept.CLEARING_TIME,
            LearningConcept.ROTOR_ANGLE,
            LearningConcept.TIME_STEP,
        ),
    )


def explain_time_step_sensitivity(
    results: Sequence[SMIBCriticalClearingTimeResult],
) -> PedagogicalExplanation:
    """Compare existing H19 brackets without rerunning the scientific paths."""
    if len(results) < 2:
        raise ValueError("time-step sensitivity requires at least two H19 results")

    comparison_signatures = tuple(
        _h19_comparison_signature(result) for result in results
    )
    if any(
        signature != comparison_signatures[0]
        for signature in comparison_signatures[1:]
    ):
        raise ValueError(
            "time-step sensitivity requires H19 results with matching "
            "physical, simulation, and search provenance except for dt_s "
            "and endpoint clearing times"
        )

    ordered = sorted(results, key=_result_dt_s, reverse=True)
    dt_values = tuple(_result_dt_s(result) for result in ordered)
    if len(set(dt_values)) != len(dt_values):
        raise ValueError("time-step sensitivity requires distinct dt_s values")

    evidence: list[ExplanationEvidence] = []
    brackets = []
    for index, (dt_s, result) in enumerate(zip(dt_values, ordered), start=1):
        prefix = f"run_{index}"
        bracket = (result.stable_t_clear_s, result.unstable_t_clear_s)
        brackets.append(bracket)
        evidence.extend(
            (
                ExplanationEvidence(
                    key=f"{prefix}_dt_s",
                    value=dt_s,
                    unit="s",
                    statement=f"Time step for comparison run {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_stable_t_clear_s",
                    value=bracket[0],
                    unit="s",
                    statement=f"Stable H19 endpoint for comparison run {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_unstable_t_clear_s",
                    value=bracket[1],
                    unit="s",
                    statement=f"Unstable H19 endpoint for comparison run {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_bracket_width_s",
                    value=result.bracket_width_s,
                    unit="s",
                    statement=(
                        f"H19 stopping bracket width for comparison run {index}."
                    ),
                ),
            )
        )

    brackets_differ = len(set(brackets)) > 1
    evidence.append(
        ExplanationEvidence(
            key="brackets_differ",
            value=brackets_differ,
            statement="Whether supplied H19 endpoint pairs differ across dt_s.",
        )
    )
    observed = (
        "Across the supplied H19 results with matching retained provenance "
        "and distinct dt_s values, the endpoint brackets differ."
        if brackets_differ
        else "Across the supplied H19 results with matching retained "
        "provenance and distinct dt_s values, the endpoint brackets are equal "
        "at the reported float values."
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.TIME_STEP_SENSITIVITY,
        title="Time-step sensitivity of temporal brackets",
        summary=(
            observed
            + " Search-bracket width and sensitivity to temporal resolution "
            "are separate numerical properties."
        ),
        evidence=tuple(evidence),
        limitations=(
            "A small H19 bracket width does not imply that the effect of dt_s "
            "is equally small.",
            "Differences between H19 endpoint brackets at distinct dt_s values "
            "are consistent with temporal-resolution sensitivity; those "
            "differences alone do not establish a software defect.",
            "H19 results do not retain the initial search bracket or "
            "max_iterations, so this explanation cannot establish from the "
            "result objects alone that dt_s was the only differing search "
            "input.",
            "This explanation compares supplied results and does not perform a "
            "convergence study or rerun the scientific solvers.",
        ),
        concepts=(
            LearningConcept.TIME_STEP,
            LearningConcept.CLEARING_TIME,
            LearningConcept.FIRST_SWING,
        ),
    )


def render_explanation_text(explanation: PedagogicalExplanation) -> str:
    """Render a deterministic plain-text view of structured evidence."""
    lines = [explanation.title, explanation.summary, "Evidence:"]
    for item in explanation.evidence:
        unit_suffix = f" {item.unit}" if item.unit is not None else ""
        lines.append(
            f"- {item.key}={item.value!r}{unit_suffix}: {item.statement}"
        )
    lines.append("Limitations:")
    lines.extend(f"- {limitation}" for limitation in explanation.limitations)
    lines.append(
        "Concepts: "
        + ", ".join(concept.value for concept in explanation.concepts)
    )
    return "\n".join(lines)


def _required_bracket(
    bracket: FirstSwingEventBracket | None,
    message: str,
) -> FirstSwingEventBracket:
    if bracket is None:
        raise ValueError(message)
    return bracket


def _event_bracket_evidence(
    prefix: str,
    bracket: FirstSwingEventBracket,
) -> tuple[ExplanationEvidence, ...]:
    values: tuple[tuple[str, EvidenceValue, str | None, str], ...] = (
        ("left_index", bracket.left_index, None, "Left sample index"),
        ("right_index", bracket.right_index, None, "Right sample index"),
        ("left_time_s", bracket.left_time_s, "s", "Left sample time"),
        ("right_time_s", bracket.right_time_s, "s", "Right sample time"),
        ("left_delta_rad", bracket.left_delta_rad, "rad", "Left rotor angle"),
        ("right_delta_rad", bracket.right_delta_rad, "rad", "Right rotor angle"),
        (
            "left_omega_dev_pu",
            bracket.left_omega_dev_pu,
            "pu",
            "Left speed deviation",
        ),
        (
            "right_omega_dev_pu",
            bracket.right_omega_dev_pu,
            "pu",
            "Right speed deviation",
        ),
    )
    return tuple(
        ExplanationEvidence(
            key=f"{prefix}_{key}",
            value=value,
            unit=unit,
            statement=f"{statement} of the event bracket.",
        )
        for key, value, unit, statement in values
    )


def _indeterminate_summary(reason: FirstSwingReason) -> str:
    if reason is FirstSwingReason.NO_POSITIVE_EXCURSION:
        detail = (
            "no positive-speed excursion was present in the assessed "
            "post-clearing samples"
        )
    elif reason is FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT:
        detail = (
            "the sampled horizon ended before either reversal or unstable-"
            "equilibrium crossing was observed"
        )
    else:
        detail = (
            "the sampled evidence did not establish whether reversal or "
            "unstable-equilibrium crossing occurred first"
        )
    return (
        "The sampled classical SMIB first swing remains INDETERMINATE because "
        f"{detail}. H24 preserves that scientific outcome."
    )


def _fault_interval_evidence(
    evaluation: SMIBClearingTimeEvaluation,
) -> tuple[tuple[ExplanationEvidence, ...], str]:
    simulation = evaluation.simulation
    fault_index = _unique_event_index(
        simulation.time_s,
        simulation.network.t_fault_s,
        event_name="t_fault_s",
    )
    clearing_index = _unique_event_index(
        simulation.time_s,
        simulation.network.t_clear_s,
        event_name="t_clear_s",
    )
    fault_speed_pu = float(simulation.omega_dev_pu[fault_index])
    clearing_speed_pu = float(simulation.omega_dev_pu[clearing_index])
    speed_increased = clearing_speed_pu > fault_speed_pu
    evidence = (
        ExplanationEvidence(
            key="fault_onset_omega_dev_pu",
            value=fault_speed_pu,
            unit="pu",
            statement="Sampled speed deviation at fault onset.",
        ),
        ExplanationEvidence(
            key="clearing_omega_dev_pu",
            value=clearing_speed_pu,
            unit="pu",
            statement="Sampled speed deviation at clearing.",
        ),
        ExplanationEvidence(
            key="fault_interval_speed_increased",
            value=speed_increased,
            statement=(
                "Whether sampled speed deviation increased from fault onset "
                "to clearing."
            ),
        ),
    )
    clause = (
        " During the modeled fault interval, sampled speed deviation "
        "increased, which is trajectory evidence of net rotor acceleration "
        "across that interval."
        if speed_increased
        else ""
    )
    return evidence, clause


def _unique_event_index(
    time_s: Iterable[float],
    event_time_s: float,
    *,
    event_name: str,
) -> int:
    indices = [
        index
        for index, sample_time_s in enumerate(time_s)
        if sample_time_s == event_time_s
    ]
    if len(indices) != 1:
        raise ValueError(f"trajectory must contain {event_name} exactly once")
    return indices[0]


def _result_dt_s(result: SMIBCriticalClearingTimeResult) -> float:
    stable_dt_s = result.stable_evaluation.simulation.dt_s
    unstable_dt_s = result.unstable_evaluation.simulation.dt_s
    if stable_dt_s != unstable_dt_s:
        raise ValueError("H19 endpoint simulations must use the same dt_s")
    return stable_dt_s


def _h19_comparison_signature(
    result: SMIBCriticalClearingTimeResult,
) -> tuple[object, ...]:
    stable_signature = _simulation_comparison_signature(
        result.stable_evaluation.simulation
    )
    unstable_signature = _simulation_comparison_signature(
        result.unstable_evaluation.simulation
    )
    if stable_signature != unstable_signature:
        raise ValueError(
            "each H19 result must have matching endpoint provenance except "
            "for t_clear_s"
        )
    return stable_signature + (result.time_tolerance_s, result.iterations)


def _simulation_comparison_signature(
    simulation: SMIBTransientSimulationResult,
) -> tuple[object, ...]:
    network = simulation.network
    return (
        simulation.parameters,
        simulation.initial_state,
        network.Pmax_prefault_pu,
        network.Pmax_fault_pu,
        network.Pmax_postfault_pu,
        network.t_fault_s,
        simulation.t_start_s,
        simulation.t_end_s,
    )
