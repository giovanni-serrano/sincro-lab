"""Deterministic local guided-learning workflows for classical SMIB cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite

from sincrolab.analysis import FirstSwingReason, FirstSwingStatus
from sincrolab.application.clearing_time import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
    evaluate_smib_clearing_time,
    search_smib_critical_clearing_time,
)
from sincrolab.application.learning import (
    LearningConcept,
    PedagogicalExplanation,
    explain_critical_clearing_time,
    explain_first_swing,
)
from sincrolab.models import SMIBInitialState, SMIBParameters, SMIBTransientNetwork


class GuidedCaseDifficulty(Enum):
    INTRODUCTORY = "introductory"
    INTERMEDIATE = "intermediate"


class GuidedCaseKind(Enum):
    LATE_CLEARING = "late_clearing"
    INERTIA_EFFECT = "inertia_effect"
    FIRST_SWING_EVIDENCE = "first_swing_evidence"


class GuidedGoalKind(Enum):
    FIRST_SWING_STATUS = "first_swing_status"
    OBSERVE_TRAJECTORY_CHANGE = "observe_trajectory_change"


@dataclass(frozen=True)
class GuidedSimulationConfig:
    parameters: SMIBParameters
    initial_state: SMIBInitialState
    network: SMIBTransientNetwork
    t_start_s: float
    t_end_s: float
    dt_s: float


@dataclass(frozen=True)
class EditableParameter:
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    baseline_value: float

    def __post_init__(self) -> None:
        values = (self.minimum, self.maximum, self.baseline_value)
        if not all(isfinite(value) for value in values):
            raise ValueError("editable parameter values must be finite")
        if self.minimum > self.maximum:
            raise ValueError("editable parameter minimum must not exceed maximum")
        if not self.minimum <= self.baseline_value <= self.maximum:
            raise ValueError("baseline value must be within editable bounds")


@dataclass(frozen=True)
class ParameterChange:
    key: str
    baseline_value: float
    attempted_value: float
    unit: str


@dataclass(frozen=True)
class SolutionSetting:
    key: str
    value: float
    unit: str


@dataclass(frozen=True)
class PedagogicalSolution:
    settings: tuple[SolutionSetting, ...]
    explanation: str
    limitation: str


@dataclass(frozen=True)
class ConceptOption:
    option_id: str
    text: str


@dataclass(frozen=True)
class ConceptQuestion:
    question_id: str
    prompt: str
    options: tuple[ConceptOption, ...]
    correct_option_id: str

    def __post_init__(self) -> None:
        option_ids = tuple(option.option_id for option in self.options)
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("concept option identifiers must be unique")
        if self.correct_option_id not in option_ids:
            raise ValueError("correct option must belong to the question")


@dataclass(frozen=True)
class GuidedGoal:
    kind: GuidedGoalKind
    target_status: FirstSwingStatus | None = None


@dataclass(frozen=True)
class GuidedCase:
    case_id: str
    kind: GuidedCaseKind
    title: str
    context: str
    learning_objective: str
    difficulty: GuidedCaseDifficulty
    baseline_config: GuidedSimulationConfig
    goal: GuidedGoal
    prediction_prompt: str
    prediction_options: tuple[str, ...]
    editable_parameters: tuple[EditableParameter, ...]
    hints: tuple[str, ...]
    pedagogical_solution: PedagogicalSolution | None
    conceptual_questions: tuple[ConceptQuestion, ...]
    debrief_concepts: tuple[LearningConcept, ...]
    provenance: str

    def __post_init__(self) -> None:
        if not self.case_id or not self.prediction_options:
            raise ValueError("guided case identifiers and predictions are required")
        keys = tuple(parameter.key for parameter in self.editable_parameters)
        if len(keys) != len(set(keys)):
            raise ValueError("editable parameter keys must be unique")
        for parameter in self.editable_parameters:
            if parameter.baseline_value != _config_value(
                self.baseline_config,
                parameter.key,
            ):
                raise ValueError(
                    "editable parameter baseline_value must match "
                    "the guided case baseline configuration"
                )
        question_ids = tuple(
            question.question_id for question in self.conceptual_questions
        )
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("concept question identifiers must be unique")
        if len(self.hints) < 2:
            raise ValueError("guided cases require at least two progressive hints")


@dataclass(frozen=True)
class PreparedGuidedAttempt:
    guided_case: GuidedCase
    prediction: str

    def __post_init__(self) -> None:
        if self.prediction not in self.guided_case.prediction_options:
            raise ValueError("prediction must be one of the guided case options")


@dataclass(frozen=True)
class ScientificComparison:
    baseline_status: FirstSwingStatus
    attempted_status: FirstSwingStatus
    baseline_reason: FirstSwingReason
    attempted_reason: FirstSwingReason
    baseline_max_delta_rad: float
    attempted_max_delta_rad: float
    baseline_max_abs_omega_dev_pu: float
    attempted_max_abs_omega_dev_pu: float


@dataclass(frozen=True)
class GoalEvaluation:
    achieved: bool
    kind: GuidedGoalKind
    observed_status: FirstSwingStatus
    target_status: FirstSwingStatus | None
    evidence: str


@dataclass(frozen=True)
class QuestionAnswer:
    question_id: str
    option_id: str


@dataclass(frozen=True)
class ConceptScore:
    correct: int
    total: int


@dataclass(frozen=True)
class LocalPrePostScore:
    pre_score: ConceptScore
    post_score: ConceptScore
    local_delta: int
    limitation: str


@dataclass(frozen=True)
class GuidedDebrief:
    summary: str
    baseline_explanation: PedagogicalExplanation
    attempted_explanation: PedagogicalExplanation
    scientific_comparison: ScientificComparison
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class AttemptRecord:
    case_id: str
    prediction: str
    baseline_config: GuidedSimulationConfig
    attempted_config: GuidedSimulationConfig
    changed_parameters: tuple[ParameterChange, ...]
    baseline_evaluation: SMIBClearingTimeEvaluation
    attempted_evaluation: SMIBClearingTimeEvaluation
    baseline_explanation: PedagogicalExplanation
    attempted_explanation: PedagogicalExplanation
    scientific_comparison: ScientificComparison
    goal_evaluation: GoalEvaluation
    hints_revealed: tuple[str, ...]
    solution_revealed: bool
    revealed_solution: PedagogicalSolution | None
    pre_answers: tuple[QuestionAnswer, ...] | None
    post_answers: tuple[QuestionAnswer, ...] | None
    pre_post_score: LocalPrePostScore | None
    critical_clearing_result: SMIBCriticalClearingTimeResult | None
    critical_clearing_explanation: PedagogicalExplanation | None
    debrief: GuidedDebrief


def default_guided_cases() -> tuple[GuidedCase, ...]:
    """Return H25's deterministic, public-input guided case catalog."""
    return (_late_clearing_case(), _inertia_case(), _first_swing_case())


def prepare_guided_attempt(
    guided_case: GuidedCase,
    prediction: str,
) -> PreparedGuidedAttempt:
    """Record a prediction before any guided scientific execution."""
    return PreparedGuidedAttempt(guided_case=guided_case, prediction=prediction)


def reveal_progressive_hints(
    guided_case: GuidedCase,
    count: int,
) -> tuple[str, ...]:
    """Reveal an ordered hint prefix without exposing a solution."""
    if count < 0 or count > len(guided_case.hints):
        raise ValueError("hint count must be within the available hint range")
    return guided_case.hints[:count]


def score_concept_answers(
    guided_case: GuidedCase,
    answers: Sequence[QuestionAnswer],
) -> ConceptScore:
    """Score local multiple-choice answers deterministically."""
    supplied = {answer.question_id: answer.option_id for answer in answers}
    if len(supplied) != len(answers):
        raise ValueError("question answers must have unique question identifiers")
    known = {question.question_id for question in guided_case.conceptual_questions}
    if set(supplied) != known:
        raise ValueError(
            "a complete assessment requires one answer for every concept question"
        )
    options_by_question = {
        question.question_id: {option.option_id for option in question.options}
        for question in guided_case.conceptual_questions
    }
    if any(
        option_id not in options_by_question[question_id]
        for question_id, option_id in supplied.items()
    ):
        raise ValueError("answer option does not belong to the concept question")
    correct = sum(
        supplied.get(question.question_id) == question.correct_option_id
        for question in guided_case.conceptual_questions
    )
    return ConceptScore(correct=correct, total=len(guided_case.conceptual_questions))


def run_guided_attempt(
    prepared: PreparedGuidedAttempt,
    changes: Mapping[str, float],
    *,
    hints_revealed: int = 0,
    reveal_solution: bool = False,
    pre_answers: Sequence[QuestionAnswer] | None = None,
    post_answers: Sequence[QuestionAnswer] | None = None,
) -> AttemptRecord:
    """Run one deterministic, local attempt through existing scientific APIs."""
    if not isinstance(prepared, PreparedGuidedAttempt):
        raise TypeError("a prepared guided attempt is required before execution")
    guided_case = prepared.guided_case
    attempted_config, changed_parameters = _apply_changes(guided_case, changes)
    baseline_evaluation = _evaluate(guided_case.baseline_config)
    attempted_evaluation = _evaluate(attempted_config)
    baseline_explanation = explain_first_swing(baseline_evaluation)
    attempted_explanation = explain_first_swing(attempted_evaluation)
    comparison = _scientific_comparison(baseline_evaluation, attempted_evaluation)
    goal_evaluation = _evaluate_goal(guided_case.goal, comparison)
    critical_result = None
    critical_explanation = None
    if guided_case.kind is GuidedCaseKind.LATE_CLEARING:
        config = guided_case.baseline_config
        critical_result = search_smib_critical_clearing_time(
            config.parameters,
            config.initial_state,
            config.network,
            stable_t_clear_s=0.2,
            unstable_t_clear_s=0.35,
            t_start_s=config.t_start_s,
            t_end_s=config.t_end_s,
            dt_s=config.dt_s,
            time_tolerance_s=1e-4,
        )
        critical_explanation = explain_critical_clearing_time(critical_result)
    if (pre_answers is None) != (post_answers is None):
        raise ValueError("pre and post assessments must be supplied together")
    recorded_pre_answers = None
    recorded_post_answers = None
    pre_post_score = None
    if pre_answers is not None and post_answers is not None:
        recorded_pre_answers = tuple(pre_answers)
        recorded_post_answers = tuple(post_answers)
        pre_score = score_concept_answers(guided_case, recorded_pre_answers)
        post_score = score_concept_answers(guided_case, recorded_post_answers)
        pre_post_score = LocalPrePostScore(
            pre_score=pre_score,
            post_score=post_score,
            local_delta=post_score.correct - pre_score.correct,
            limitation=(
                "A pre/post score change for one local attempt does not establish "
                "educational effectiveness."
            ),
        )
    debrief = _build_debrief(
        guided_case,
        changed_parameters,
        baseline_explanation,
        attempted_explanation,
        comparison,
    )
    return AttemptRecord(
        case_id=guided_case.case_id,
        prediction=prepared.prediction,
        baseline_config=guided_case.baseline_config,
        attempted_config=attempted_config,
        changed_parameters=changed_parameters,
        baseline_evaluation=baseline_evaluation,
        attempted_evaluation=attempted_evaluation,
        baseline_explanation=baseline_explanation,
        attempted_explanation=attempted_explanation,
        scientific_comparison=comparison,
        goal_evaluation=goal_evaluation,
        hints_revealed=reveal_progressive_hints(guided_case, hints_revealed),
        solution_revealed=reveal_solution,
        revealed_solution=(guided_case.pedagogical_solution if reveal_solution else None),
        pre_answers=recorded_pre_answers,
        post_answers=recorded_post_answers,
        pre_post_score=pre_post_score,
        critical_clearing_result=critical_result,
        critical_clearing_explanation=critical_explanation,
        debrief=debrief,
    )


def _apply_changes(
    guided_case: GuidedCase,
    changes: Mapping[str, float],
) -> tuple[GuidedSimulationConfig, tuple[ParameterChange, ...]]:
    editable = {parameter.key: parameter for parameter in guided_case.editable_parameters}
    if not set(changes) <= set(editable):
        raise ValueError("attempt contains a parameter that is not editable")
    config = guided_case.baseline_config
    recorded: list[ParameterChange] = []
    for key in (parameter.key for parameter in guided_case.editable_parameters):
        if key not in changes:
            continue
        value = float(changes[key])
        parameter = editable[key]
        if not isfinite(value) or not parameter.minimum <= value <= parameter.maximum:
            raise ValueError(f"{key} must be finite and within its editable bounds")
        baseline_value = _config_value(config, key)
        config = _replace_config_value(config, key, value)
        if value != baseline_value:
            recorded.append(
                ParameterChange(key, baseline_value, value, parameter.unit)
            )
    return config, tuple(recorded)


def _config_value(config: GuidedSimulationConfig, key: str) -> float:
    if key == "H_s":
        return config.parameters.H_s
    if key == "t_clear_s":
        return config.network.t_clear_s
    raise ValueError("unsupported guided parameter key")


def _replace_config_value(
    config: GuidedSimulationConfig,
    key: str,
    value: float,
) -> GuidedSimulationConfig:
    if key == "H_s":
        return replace(config, parameters=replace(config.parameters, H_s=value))
    if key == "t_clear_s":
        return replace(config, network=replace(config.network, t_clear_s=value))
    raise ValueError("unsupported guided parameter key")


def _evaluate(config: GuidedSimulationConfig) -> SMIBClearingTimeEvaluation:
    return evaluate_smib_clearing_time(
        config.parameters,
        config.initial_state,
        config.network,
        t_clear_s=config.network.t_clear_s,
        t_start_s=config.t_start_s,
        t_end_s=config.t_end_s,
        dt_s=config.dt_s,
    )


def _scientific_comparison(
    baseline: SMIBClearingTimeEvaluation,
    attempted: SMIBClearingTimeEvaluation,
) -> ScientificComparison:
    baseline_simulation = baseline.simulation
    attempted_simulation = attempted.simulation
    return ScientificComparison(
        baseline_status=baseline.first_swing.status,
        attempted_status=attempted.first_swing.status,
        baseline_reason=baseline.first_swing.reason,
        attempted_reason=attempted.first_swing.reason,
        baseline_max_delta_rad=float(baseline_simulation.delta_rad.max()),
        attempted_max_delta_rad=float(attempted_simulation.delta_rad.max()),
        baseline_max_abs_omega_dev_pu=float(
            abs(baseline_simulation.omega_dev_pu).max()
        ),
        attempted_max_abs_omega_dev_pu=float(
            abs(attempted_simulation.omega_dev_pu).max()
        ),
    )


def _evaluate_goal(
    goal: GuidedGoal,
    comparison: ScientificComparison,
) -> GoalEvaluation:
    if goal.kind is GuidedGoalKind.FIRST_SWING_STATUS:
        achieved = comparison.attempted_status is goal.target_status
        evidence = (
            "The attempted H15 first-swing status matches the guided target."
            if achieved
            else "The attempted H15 first-swing status does not match the guided target."
        )
    else:
        achieved = (
            comparison.attempted_max_delta_rad != comparison.baseline_max_delta_rad
            or comparison.attempted_max_abs_omega_dev_pu
            != comparison.baseline_max_abs_omega_dev_pu
        )
        evidence = (
            "The sampled trajectory metrics differ from the baseline."
            if achieved
            else "The sampled trajectory metrics do not differ from the baseline."
        )
    return GoalEvaluation(
        achieved=achieved,
        kind=goal.kind,
        observed_status=comparison.attempted_status,
        target_status=goal.target_status,
        evidence=evidence,
    )


def _build_debrief(
    guided_case: GuidedCase,
    changes: tuple[ParameterChange, ...],
    baseline_explanation: PedagogicalExplanation,
    attempted_explanation: PedagogicalExplanation,
    comparison: ScientificComparison,
) -> GuidedDebrief:
    if guided_case.kind is GuidedCaseKind.INERTIA_EFFECT:
        if tuple(change.key for change in changes) == ("H_s",):
            summary = (
                "Only H_s changed in this controlled modeled comparison; the "
                "reported trajectory metrics show the response observed for this case."
            )
        else:
            summary = (
                "No exclusive effect is attributed to H_s because this attempt did "
                "not contain exactly one recorded H_s change."
            )
        limitations = (
            "This single modeled comparison does not imply that higher inertia always "
            "produces first-swing stability.",
            "The result is specific to the classical SMIB model and supplied event.",
        )
    elif guided_case.kind is GuidedCaseKind.LATE_CLEARING:
        summary = (
            "The attempted clearing time is evaluated by H18 and its sampled "
            "first-swing outcome is interpreted by H24."
        )
        limitations = (
            "H19 bounds a transition between stable and unstable endpoints; it does "
            "not provide an exact CCT.",
            "time_tolerance_s is a search stopping criterion, not physical uncertainty.",
        )
    else:
        summary = (
            "H15 supplies the attempted status, reason, and event evidence; H24 "
            "interprets them without changing the classification."
        )
        limitations = (
            "The classification concerns the first swing of one sampled classical "
            "SMIB trajectory, not global or multimachine stability.",
        )
    return GuidedDebrief(
        summary=summary,
        baseline_explanation=baseline_explanation,
        attempted_explanation=attempted_explanation,
        scientific_comparison=comparison,
        limitations=limitations,
    )


def _base_config(*, H_s: float = 3.5, t_clear_s: float = 0.2) -> GuidedSimulationConfig:
    return GuidedSimulationConfig(
        parameters=SMIBParameters(H_s=H_s, D_pu=0.2, f_base_hz=60.0, Pm_pu=0.7),
        initial_state=SMIBInitialState(
            delta_rad=0.622826585412003,
            omega_dev_pu=0.0,
        ),
        network=SMIBTransientNetwork(
            Pmax_prefault_pu=1.2,
            Pmax_fault_pu=0.2,
            Pmax_postfault_pu=1.1,
            t_fault_s=0.1,
            t_clear_s=t_clear_s,
        ),
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
    )


def _questions() -> tuple[ConceptQuestion, ...]:
    return (
        ConceptQuestion(
            question_id="accelerating_power",
            prompt=(
                "When net accelerating power is positive during the disturbance, "
                "what is the immediate effect?"
            ),
            options=(
                ConceptOption("a", "Rotor speed deviation tends to increase."),
                ConceptOption("b", "Rotor angle becomes globally stable by definition."),
                ConceptOption("c", "The H19 bracket becomes exact."),
            ),
            correct_option_id="a",
        ),
        ConceptQuestion(
            question_id="first_swing_evidence",
            prompt="Which evidence supports a sampled stable first-swing classification?",
            options=(
                ConceptOption("a", "Crossing before reversal."),
                ConceptOption("b", "Reversal before crossing."),
                ConceptOption("c", "A small H19 search tolerance alone."),
            ),
            correct_option_id="b",
        ),
    )


def _late_clearing_case() -> GuidedCase:
    return GuidedCase(
        case_id="late-clearing-bracket",
        kind=GuidedCaseKind.LATE_CLEARING,
        title="Clearing time and the temporal transition bracket",
        context=(
            "A synthetic classical SMIB disturbance is cleared at a selectable time."
        ),
        learning_objective=(
            "Relate early and late clearing to H15 outcomes and interpret H19 as a "
            "stable-to-unstable bracket."
        ),
        difficulty=GuidedCaseDifficulty.INTRODUCTORY,
        baseline_config=_base_config(t_clear_s=0.35),
        goal=GuidedGoal(
            GuidedGoalKind.FIRST_SWING_STATUS,
            FirstSwingStatus.STABLE,
        ),
        prediction_prompt="Predict the attempted sampled first-swing outcome.",
        prediction_options=("stable", "unstable", "indeterminate"),
        editable_parameters=(
            EditableParameter(
                "t_clear_s", "Clearing time", "s", 0.15, 0.4, 0.35
            ),
        ),
        hints=(
            "Compare how long accelerating power acts before the network is cleared.",
            "Use the H19 stable and unstable endpoints as bounds, not as one exact time.",
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("t_clear_s", 0.2, "s"),),
            explanation=(
                "One pedagogical solution is to try the modeled clearing time 0.2 s "
                "and inspect the H15 result."
            ),
            limitation=(
                "This is one synthetic educational intervention, not a protection "
                "setting or recommendation for a real system."
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.CLEARING_TIME,
            LearningConcept.FIRST_SWING,
            LearningConcept.ROTOR_ANGLE,
        ),
        provenance=(
            "Synthetic public SMIB input family used by SincroLab reference cases; "
            "scientific outcomes are recomputed through H18/H19."
        ),
    )


def _inertia_case() -> GuidedCase:
    return GuidedCase(
        case_id="controlled-inertia-effect",
        kind=GuidedCaseKind.INERTIA_EFFECT,
        title="Controlled effect of inertia",
        context=(
            "Two executions retain the same machine input, network, event, initial "
            "state, horizon, and time step while H_s may change."
        ),
        learning_objective=(
            "Observe how changing only H_s changes sampled trajectory evidence in "
            "this modeled case."
        ),
        difficulty=GuidedCaseDifficulty.INTERMEDIATE,
        baseline_config=_base_config(H_s=3.5, t_clear_s=0.28),
        goal=GuidedGoal(GuidedGoalKind.OBSERVE_TRAJECTORY_CHANGE),
        prediction_prompt="Predict how the sampled response will compare with baseline.",
        prediction_options=("smaller excursion", "larger excursion", "no change"),
        editable_parameters=(
            EditableParameter("H_s", "Inertia constant", "s", 2.0, 8.0, 3.5),
        ),
        hints=(
            "Hold the event and all other retained inputs fixed while changing H_s.",
            "Compare maximum rotor angle and absolute speed deviation; do not assume a status.",
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("H_s", 6.0, "s"),),
            explanation=(
                "One pedagogical solution is to try H_s = 6.0 s and compare the "
                "sampled trajectory metrics with the baseline."
            ),
            limitation=(
                "This modeled example does not establish that higher inertia always "
                "produces stability or prescribe a real machine parameter."
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.ROTOR_ANGLE,
            LearningConcept.SPEED_DEVIATION,
            LearningConcept.FIRST_SWING,
        ),
        provenance=(
            "Synthetic public SMIB input family with a controlled H_s intervention; "
            "H18 and H15 recompute both trajectories."
        ),
    )


def _first_swing_case() -> GuidedCase:
    return GuidedCase(
        case_id="first-swing-event-evidence",
        kind=GuidedCaseKind.FIRST_SWING_EVIDENCE,
        title="Stable and unstable first-swing evidence",
        context=(
            "A synthetic classical SMIB trajectory exposes H15 event ordering for "
            "different clearing times."
        ),
        learning_objective=(
            "Distinguish reversal-before-crossing from crossing-before-reversal using "
            "the status, reason, event brackets, and speed evidence retained by H15."
        ),
        difficulty=GuidedCaseDifficulty.INTRODUCTORY,
        baseline_config=_base_config(t_clear_s=0.2),
        goal=GuidedGoal(
            GuidedGoalKind.FIRST_SWING_STATUS,
            FirstSwingStatus.UNSTABLE,
        ),
        prediction_prompt="Predict the attempted sampled first-swing outcome.",
        prediction_options=("stable", "unstable", "indeterminate"),
        editable_parameters=(
            EditableParameter(
                "t_clear_s", "Clearing time", "s", 0.2, 0.35, 0.2
            ),
        ),
        hints=(
            "Look for whether speed reverses before the unstable equilibrium is crossed.",
            "H15 classifies event order from sampled brackets and retains its reason.",
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("t_clear_s", 0.35, "s"),),
            explanation=(
                "One pedagogical solution is to try the modeled clearing time 0.35 s "
                "and inspect H15's crossing and speed evidence."
            ),
            limitation=(
                "The result concerns one sampled first swing in a synthetic classical "
                "SMIB case, not global or multimachine stability."
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.FIRST_SWING,
            LearningConcept.UNSTABLE_EQUILIBRIUM,
            LearningConcept.SPEED_DEVIATION,
        ),
        provenance=(
            "Synthetic public stable/unstable SMIB input family used by SincroLab "
            "reference cases; H18/H15 recompute each attempted outcome."
        ),
    )
