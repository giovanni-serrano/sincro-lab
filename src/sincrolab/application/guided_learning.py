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
from sincrolab.application.learning_content import meaning, quantity
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
                "Un cambio de puntuación pre/post en un intento local no demuestra eficacia educativa."
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
            "El diagnóstico de primera oscilación del intento cumple el objetivo del caso."
            if achieved
            else (
                "El diagnóstico de primera oscilación del intento todavía no cumple el "
                "objetivo del caso."
            )
        )
    else:
        achieved = (
            comparison.attempted_max_delta_rad != comparison.baseline_max_delta_rad
            or comparison.attempted_max_abs_omega_dev_pu
            != comparison.baseline_max_abs_omega_dev_pu
        )
        evidence = (
            "Las métricas de la trayectoria muestreada difieren de la configuración inicial."
            if achieved
            else "Las métricas de la trayectoria muestreada no difieren de la configuración inicial."
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
                (
                    "Solo cambió la inercia H en esta comparación controlada del modelo; las "
                    "métricas reportadas muestran la respuesta observada para este caso."
                )
            )
        else:
            summary = (
                (
                    "No se atribuye un efecto exclusivo a la inercia H porque el intento no "
                    "registra exactamente un cambio de esa variable."
                )
            )
        limitations = (
            (
                "Esta comparación aislada no implica que una mayor inercia siempre produzca "
                "estabilidad de primera oscilación."
            ),
            "El resultado es específico del modelo clásico SMIB y del evento suministrado.",
        )
    elif guided_case.kind is GuidedCaseKind.LATE_CLEARING:
        summary = (
            (
                "El instante de despeje del intento determina cuándo comienza la posfalla. Su"
                " resultado de primera oscilación se interpreta con las muestras calculadas."
            )
        )
        limitations = (
            (
                "La búsqueda acota una transición entre extremos estable e inestable; no "
                "proporciona un CCT exacto."
            ),
            "La tolerancia de búsqueda es un criterio de parada, no incertidumbre física.",
        )
    else:
        summary = (
            (
                "El diagnóstico conserva el estado, la razón y la evidencia de eventos del "
                "intento. La explicación los interpreta sin modificar la clasificación."
            )
        )
        limitations = (
            (
                "La clasificación corresponde a la primera oscilación de una trayectoria "
                "clásica SMIB muestreada, no a estabilidad global o multimáquina."
            ),
        )
    # These values come from the retained comparison, never from a UI estimate.
    changed_text = "; ".join(
        f"{quantity(change.key).label}: {change.baseline_value:g} → "
        f"{change.attempted_value:g} {change.unit}"
        for change in changes
    ) or "Sin cambios de parámetros respecto a la configuración inicial."
    summary += (
        f" {changed_text} Diagnóstico inicial: {meaning(comparison.baseline_status.value).label}; "
        f"intento: {meaning(comparison.attempted_status.value).label}. "
        f"Máximo ángulo en la ventana: {comparison.baseline_max_delta_rad:.6g} → "
        f"{comparison.attempted_max_delta_rad:.6g} rad. Máxima desviación absoluta "
        f"de velocidad: {comparison.baseline_max_abs_omega_dev_pu:.6g} → "
        f"{comparison.attempted_max_abs_omega_dev_pu:.6g} pu."
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
                (
                    "Cuando la potencia acelerante neta es positiva durante la perturbación, "
                    "¿cuál es el efecto inmediato?"
                )
            ),
            options=(
                ConceptOption("a", "La desviación de velocidad del rotor tiende a aumentar."),
                ConceptOption("b", "El ángulo del rotor se vuelve globalmente estable por definición."),
                ConceptOption("c", "El intervalo crítico de despeje se vuelve exacto."),
            ),
            correct_option_id="a",
        ),
        ConceptQuestion(
            question_id="first_swing_evidence",
            prompt="¿Qué evidencia respalda una primera oscilación muestreada estable?",
            options=(
                ConceptOption("a", "Cruce antes de la reversión."),
                ConceptOption("b", "Reversión antes del cruce."),
                ConceptOption("c", "Solo una tolerancia pequeña de búsqueda temporal."),
            ),
            correct_option_id="b",
        ),
    )


def _late_clearing_case() -> GuidedCase:
    return GuidedCase(
        case_id="late-clearing-bracket",
        kind=GuidedCaseKind.LATE_CLEARING,
        title="Efecto del tiempo de despeje",
        context=(
            (
                "Una perturbación sintética del modelo clásico SMIB se despeja en un instante"
                " que puedes modificar."
            )
        ),
        learning_objective=(
            (
                "Relaciona despejes tempranos y tardíos con la primera oscilación e "
                "interpreta el intervalo entre extremos estable e inestable."
            )
        ),
        difficulty=GuidedCaseDifficulty.INTRODUCTORY,
        baseline_config=_base_config(t_clear_s=0.35),
        goal=GuidedGoal(
            GuidedGoalKind.FIRST_SWING_STATUS,
            FirstSwingStatus.STABLE,
        ),
        prediction_prompt=(
            "Predice el resultado de la primera oscilación muestreada para la configuración "
            "que vas a ejecutar."
        ),
        prediction_options=("stable", "unstable", "indeterminate"),
        editable_parameters=(
            EditableParameter(
                "t_clear_s", quantity("t_clear_s").label, "s", 0.15, 0.4, 0.35
            ),
        ),
        hints=(
            "Compara cuánto tiempo actúa el balance acelerante antes de despejar la falla.",
            (
                "Usa los extremos estable e inestable de la búsqueda como límites de un "
                "intervalo, no como un tiempo exacto."
            ),
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("t_clear_s", 0.2, "s"),),
            explanation=(
                (
                    "Una solución pedagógica posible es probar un despeje a 0.2 s y examinar "
                    "el diagnóstico. Al terminar antes el intervalo de falla, cambia el "
                    "estado con que comienza la posfalla; comprueba su efecto en la velocidad"
                    " y el orden de eventos calculados."
                )
            ),
            limitation=(
                (
                    "Es una intervención educativa sintética posible, no un ajuste de "
                    "protección ni una recomendación para una red real. Otras combinaciones "
                    "pueden producir respuestas distintas."
                )
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.CLEARING_TIME,
            LearningConcept.FIRST_SWING,
            LearningConcept.ROTOR_ANGLE,
        ),
        provenance=(
            (
                "Familia sintética pública de entradas SMIB utilizada por los casos de "
                "referencia de SincroLab; las trayectorias y los extremos críticos se "
                "recalculan con el mismo núcleo."
            )
        ),
    )


def _inertia_case() -> GuidedCase:
    return GuidedCase(
        case_id="controlled-inertia-effect",
        kind=GuidedCaseKind.INERTIA_EFFECT,
        title="Efecto controlado de la inercia",
        context=(
            (
                "Dos ejecuciones conservan potencia, amortiguamiento, frecuencia, red, "
                "evento, estado inicial, horizonte y paso temporal; solo puede cambiar la "
                "inercia H."
            )
        ),
        learning_objective=(
            (
                "Observa cómo cambiar únicamente la inercia H modifica la evidencia de las "
                "trayectorias en este caso modelado."
            )
        ),
        difficulty=GuidedCaseDifficulty.INTERMEDIATE,
        baseline_config=_base_config(H_s=3.5, t_clear_s=0.28),
        goal=GuidedGoal(GuidedGoalKind.OBSERVE_TRAJECTORY_CHANGE),
        prediction_prompt=(
            "Predice cómo se comparará la respuesta muestreada con la configuración inicial. "
            "Después contrasta los máximos de ángulo y desviación absoluta de velocidad; esta"
            " predicción no asigna un estado de estabilidad."
        ),
        prediction_options=("smaller excursion", "larger excursion", "no change"),
        editable_parameters=(
            EditableParameter("H_s", quantity("H_s").label, "s", 2.0, 8.0, 3.5),
        ),
        hints=(
            "Mantén fijos el evento y las demás entradas mientras exploras la respuesta del rotor.",
            (
                "Compara el máximo ángulo del rotor y la máxima desviación absoluta de "
                "velocidad de la ventana; no presupongas un estado de estabilidad."
            ),
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("H_s", 6.0, "s"),),
            explanation=(
                (
                    "Una solución pedagógica posible es probar H = 6.0 s y comparar las "
                    "métricas muestreadas con la configuración inicial. H divide el balance "
                    "neto en la ecuación de aceleración; compara ambas trayectorias para "
                    "verificar el efecto de esta intervención."
                )
            ),
            limitation=(
                (
                    "Este ejemplo no demuestra que una mayor inercia siempre produzca "
                    "estabilidad ni prescribe un parámetro para una máquina real. Es una "
                    "comparación educativa posible."
                )
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.ROTOR_ANGLE,
            LearningConcept.SPEED_DEVIATION,
            LearningConcept.FIRST_SWING,
        ),
        provenance=(
            (
                "Familia sintética pública de entradas SMIB con una intervención controlada "
                "en la inercia; ambas trayectorias se recalculan con el mismo núcleo."
            )
        ),
    )


def _first_swing_case() -> GuidedCase:
    return GuidedCase(
        case_id="first-swing-event-evidence",
        kind=GuidedCaseKind.FIRST_SWING_EVIDENCE,
        title="Reconocer la estabilidad de primera oscilación",
        context=(
            (
                "Una trayectoria sintética del modelo clásico SMIB permite observar el orden "
                "de reversión y cruce para distintos tiempos de despeje."
            )
        ),
        learning_objective=(
            (
                "Distingue una reversión antes del cruce de un cruce antes de la reversión "
                "usando diagnóstico, intervalos de muestras y desviación de velocidad."
            )
        ),
        difficulty=GuidedCaseDifficulty.INTRODUCTORY,
        baseline_config=_base_config(t_clear_s=0.2),
        goal=GuidedGoal(
            GuidedGoalKind.FIRST_SWING_STATUS,
            FirstSwingStatus.UNSTABLE,
        ),
        prediction_prompt=(
            "Predice el resultado de la primera oscilación muestreada para la configuración "
            "que vas a ejecutar."
        ),
        prediction_options=("stable", "unstable", "indeterminate"),
        editable_parameters=(
            EditableParameter(
                "t_clear_s", quantity("t_clear_s").label, "s", 0.2, 0.35, 0.2
            ),
        ),
        hints=(
            "Busca si la desviación de velocidad revierte antes de cruzar el equilibrio inestable.",
            (
                "El diagnóstico utiliza el orden de eventos en intervalos de muestras y "
                "conserva la razón observada; examina las dos velocidades del intervalo de "
                "cruce."
            ),
        ),
        pedagogical_solution=PedagogicalSolution(
            settings=(SolutionSetting("t_clear_s", 0.35, "s"),),
            explanation=(
                (
                    "Una solución pedagógica posible es probar un despeje a 0.35 s y examinar"
                    " la evidencia de cruce y velocidad. La falla dura más que en la "
                    "configuración inicial; contrasta cómo cambia el estado al despejar y qué"
                    " evento ocurre primero."
                )
            ),
            limitation=(
                (
                    "El resultado concierne a una primera oscilación muestreada de un caso "
                    "SMIB sintético, no a estabilidad global o multimáquina. Es una "
                    "intervención educativa posible."
                )
            ),
        ),
        conceptual_questions=_questions(),
        debrief_concepts=(
            LearningConcept.FIRST_SWING,
            LearningConcept.UNSTABLE_EQUILIBRIUM,
            LearningConcept.SPEED_DEVIATION,
        ),
        provenance=(
            (
                "Familia sintética pública de entradas SMIB estables/inestables usada por los"
                " casos de referencia de SincroLab; cada intento recalcula su resultado con "
                "el mismo núcleo."
            )
        ),
    )
