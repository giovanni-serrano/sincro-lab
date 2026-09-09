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
            statement="Diagnóstico de primera oscilación a partir de las muestras.",
        ),
        ExplanationEvidence(
            key="reason",
            value=assessment.reason.value,
            statement="Razón observada que sustenta el diagnóstico.",
        ),
        ExplanationEvidence(
            key="delta_stable_post_rad",
            value=assessment.delta_stable_post_rad,
            unit="rad",
            statement="Ángulo de equilibrio estable posfalla relevante.",
        ),
        ExplanationEvidence(
            key="delta_unstable_post_rad",
            value=assessment.delta_unstable_post_rad,
            unit="rad",
            statement="Ángulo de equilibrio inestable posfalla relevante.",
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
            (
                "La trayectoria muestreada del modelo clásico SMIB se clasificó como estable "
                "en la primera oscilación. Tras una excursión con desviación de velocidad "
                "positiva, se observó una reversión antes de cruzar el equilibrio inestable "
                "posfalla relevante."
            )
            + fault_clause
        )
    elif assessment.status is FirstSwingStatus.UNSTABLE:
        bracket = _required_bracket(
            assessment.crossing_bracket,
            "UNSTABLE assessment requires a crossing bracket",
        )
        evidence.extend(_event_bracket_evidence("crossing", bracket))
        summary = (
            (
                "La trayectoria muestreada del modelo clásico SMIB se clasificó como "
                "inestable en la primera oscilación. Alcanzó el equilibrio inestable posfalla"
                " relevante antes de una reversión, con desviación de velocidad positiva en "
                "las dos muestras del intervalo de cruce."
            )
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
                    (
                        " La reversión y el cruce del equilibrio inestable se observaron en "
                        "el mismo par de muestras adyacentes; su orden continuo no está "
                        "resuelto."
                    )
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
                                "Se observó una reversión en el intervalo de muestras ambiguo."
                            ),
                        ),
                        ExplanationEvidence(
                            key="crossing_observed_in_ambiguous_bracket",
                            value=True,
                            statement=(
                                (
                                    "Se observó el cruce del equilibrio inestable en el "
                                    "intervalo de muestras ambiguo."
                                )
                            ),
                        ),
                        ExplanationEvidence(
                            key="ambiguous_events_share_sampled_bracket",
                            value=True,
                            statement=(
                                "Los dos eventos candidatos comparten el mismo par de muestras adyacentes."
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
        title="Interpretación de la primera oscilación",
        summary=summary,
        evidence=tuple(evidence),
        limitations=(
            (
                "El estado corresponde solo a la primera excursión creciente muestreada; no "
                "demuestra estabilidad asintótica ni global."
            ),
            (
                "Los intervalos de evento contienen muestras adyacentes de la trayectoria; no"
                " son tiempos continuos interpolados."
            ),
            (
                "La interpretación corresponde al modelo clásico SMIB y no es una conclusión "
                "general para sistemas multimáquina."
            ),
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
            statement="Extremo inferior con diagnóstico estable de primera oscilación.",
        ),
        ExplanationEvidence(
            key="stable_status",
            value=result.stable_evaluation.first_swing.status.value,
            statement="Diagnóstico de primera oscilación en el extremo inferior.",
        ),
        ExplanationEvidence(
            key="stable_reason",
            value=result.stable_evaluation.first_swing.reason.value,
            statement="Razón del diagnóstico en el extremo inferior.",
        ),
        ExplanationEvidence(
            key="unstable_t_clear_s",
            value=result.unstable_t_clear_s,
            unit="s",
            statement="Extremo superior con diagnóstico inestable de primera oscilación.",
        ),
        ExplanationEvidence(
            key="unstable_status",
            value=result.unstable_evaluation.first_swing.status.value,
            statement="Diagnóstico de primera oscilación en el extremo superior.",
        ),
        ExplanationEvidence(
            key="unstable_reason",
            value=result.unstable_evaluation.first_swing.reason.value,
            statement="Razón del diagnóstico en el extremo superior.",
        ),
        ExplanationEvidence(
            key="bracket_width_s",
            value=result.bracket_width_s,
            unit="s",
            statement="Ancho del intervalo temporal final entre extremos estable e inestable.",
        ),
        ExplanationEvidence(
            key="time_tolerance_s",
            value=result.time_tolerance_s,
            unit="s",
            statement="Criterio de parada utilizado por la búsqueda por bisección.",
        ),
        ExplanationEvidence(
            key="iterations",
            value=result.iterations,
            statement="Número de evaluaciones de puntos medios realizadas por la búsqueda.",
        ),
        ExplanationEvidence(
            key="dt_s",
            value=_result_dt_s(result),
            unit="s",
            statement="Paso temporal utilizado por las simulaciones de ambos extremos.",
        ),
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.CRITICAL_CLEARING_TIME,
        title="Intervalo crítico de tiempo de despeje",
        summary=(
            (
                "Con la configuración numérica suministrada, la búsqueda encontró una primera"
                " oscilación estable en el extremo inferior de despeje y una inestable en el "
                "extremo superior. La transición queda acotada entre esos tiempos evaluados "
                "bajo el procedimiento de búsqueda utilizado."
            )
        ),
        evidence=evidence,
        limitations=(
            (
                "La tolerancia de búsqueda es un criterio de parada de bisección, no "
                "incertidumbre física ni una estimación del error de integración."
            ),
            (
                "El punto medio es solo un resumen numérico del intervalo y no debe "
                "presentarse como el tiempo crítico de despeje."
            ),
            "Un intervalo estrecho no demuestra convergencia respecto al paso temporal.",
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
        (
            "El ángulo crítico analítico es consistente con los ángulos de los extremos "
            "temporales bajo la tolerancia angular de comparación indicada."
        )
        if result.is_consistent
        else (
            "El ángulo crítico analítico no es consistente con los ángulos de los extremos "
            "temporales bajo la tolerancia angular de comparación indicada."
        )
    )
    evidence = (
        ExplanationEvidence(
            key="analytic_critical_angle_rad",
            value=result.critical_angle_rad,
            unit="rad",
            statement="Ángulo crítico por áreas iguales obtenido por la ruta analítica.",
        ),
        ExplanationEvidence(
            key="temporal_stable_t_clear_s",
            value=result.clearing_time_result.stable_t_clear_s,
            unit="s",
            statement="Tiempo del extremo estable del intervalo temporal.",
        ),
        ExplanationEvidence(
            key="temporal_unstable_t_clear_s",
            value=result.clearing_time_result.unstable_t_clear_s,
            unit="s",
            statement="Tiempo del extremo inestable del intervalo temporal.",
        ),
        ExplanationEvidence(
            key="temporal_stable_clearing_angle_rad",
            value=result.stable_clearing_angle_rad,
            unit="rad",
            statement="Ángulo de despeje muestreado en la trayectoria del extremo estable.",
        ),
        ExplanationEvidence(
            key="temporal_unstable_clearing_angle_rad",
            value=result.unstable_clearing_angle_rad,
            unit="rad",
            statement=(
                "Ángulo de despeje muestreado en la trayectoria del extremo inestable."
            ),
        ),
        ExplanationEvidence(
            key="stable_angle_gap_rad",
            value=result.stable_angle_gap_rad,
            unit="rad",
            statement=(
                "Ángulo analítico menos ángulo de despeje del extremo estable."
            ),
        ),
        ExplanationEvidence(
            key="unstable_angle_gap_rad",
            value=result.unstable_angle_gap_rad,
            unit="rad",
            statement=(
                "Ángulo de despeje del extremo inestable menos ángulo analítico."
            ),
        ),
        ExplanationEvidence(
            key="temporal_angle_bracket_width_rad",
            value=result.clearing_angle_bracket_width_rad,
            unit="rad",
            statement="Separación entre los ángulos de despeje de los extremos temporales.",
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
            statement="Tolerancia angular utilizada únicamente para esta comparación.",
        ),
    )
    summary = (
        (
            "La comparación conserva dos rutas separadas: áreas iguales produce un ángulo "
            "crítico analítico; la búsqueda temporal produce un intervalo estable/inestable "
            "cuyas trayectorias aportan los ángulos de despeje. "
        )
        + consistency_statement
    )
    confidence_limitation = (
        (
            "La concordancia observada aumenta la confianza en este caso configurado; no "
            "demuestra validez universal del modelo."
        )
        if result.is_consistent
        else (
            "La discrepancia permanece visible para investigarla; la explicación no "
            "reconcilia ni sustituye ninguna de las dos rutas científicas."
        )
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.CRITICAL_CLEARING_CROSS_CHECK,
        title="Comparación de áreas iguales y búsqueda temporal",
        summary=summary,
        evidence=evidence,
        limitations=(
            (
                "La comparación se aplica al caso clásico compatible con áreas iguales y "
                "amortiguamiento nulo."
            ),
            "La ruta analítica no fija ni modifica los extremos de la búsqueda temporal.",
            (
                "Los extremos temporales siguen siendo evidencia de trayectorias RK4; no son "
                "oráculos analíticos."
            ),
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
                    statement=f"Paso temporal de la ejecución comparada {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_stable_t_clear_s",
                    value=bracket[0],
                    unit="s",
                    statement=f"Extremo estable de la ejecución comparada {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_unstable_t_clear_s",
                    value=bracket[1],
                    unit="s",
                    statement=f"Extremo inestable de la ejecución comparada {index}.",
                ),
                ExplanationEvidence(
                    key=f"{prefix}_bracket_width_s",
                    value=result.bracket_width_s,
                    unit="s",
                    statement=(
                        f"Ancho del intervalo de parada de la ejecución comparada {index}."
                    ),
                ),
            )
        )

    brackets_differ = len(set(brackets)) > 1
    evidence.append(
        ExplanationEvidence(
            key="brackets_differ",
            value=brackets_differ,
            statement="Indica si los pares de extremos suministrados difieren entre pasos temporales.",
        )
    )
    observed = (
        (
            "Entre los resultados suministrados con procedencia conservada coincidente y "
            "distintos pasos temporales, los intervalos de extremos difieren."
        )
        if brackets_differ
        else (
            "Entre los resultados suministrados con procedencia conservada coincidente y "
            "distintos pasos temporales, los intervalos de extremos son iguales en los "
            "valores numéricos reportados."
        )
    )
    return PedagogicalExplanation(
        kind=ExplanationKind.TIME_STEP_SENSITIVITY,
        title="Sensibilidad de los intervalos al paso temporal",
        summary=(
            observed
            + (
                " El ancho del intervalo de búsqueda y la sensibilidad a la resolución "
                "temporal son propiedades numéricas distintas."
            )
        ),
        evidence=tuple(evidence),
        limitations=(
            (
                "Un ancho de intervalo pequeño no implica que el efecto del paso temporal sea"
                " igualmente pequeño."
            ),
            (
                "Las diferencias entre intervalos de extremos con distintos pasos son "
                "compatibles con sensibilidad a la resolución temporal; por sí solas no "
                "demuestran un defecto del software."
            ),
            (
                "Los resultados no conservan el intervalo inicial de búsqueda ni el límite de"
                " iteraciones; estos objetos por sí solos no permiten establecer que el paso "
                "temporal fuera la única entrada de búsqueda diferente."
            ),
            (
                "Esta explicación compara resultados suministrados; no realiza un estudio de "
                "convergencia ni vuelve a ejecutar los integradores."
            ),
        ),
        concepts=(
            LearningConcept.TIME_STEP,
            LearningConcept.CLEARING_TIME,
            LearningConcept.FIRST_SWING,
        ),
    )


def render_explanation_text(explanation: PedagogicalExplanation) -> str:
    """Render a deterministic plain-text view of structured evidence."""
    lines = [explanation.title, explanation.summary, "Evidencia avanzada:"]
    for item in explanation.evidence:
        unit_suffix = f" {item.unit}" if item.unit is not None else ""
        lines.append(
            f"- {item.key}={item.value!r}{unit_suffix}: {item.statement}"
        )
    lines.append("Limitaciones:")
    lines.extend(f"- {limitation}" for limitation in explanation.limitations)
    lines.append(
        "Conceptos (identificadores técnicos): "
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
        ("left_index", bracket.left_index, None, "Índice de la muestra izquierda"),
        ("right_index", bracket.right_index, None, "Índice de la muestra derecha"),
        ("left_time_s", bracket.left_time_s, "s", "Tiempo de la muestra izquierda"),
        ("right_time_s", bracket.right_time_s, "s", "Tiempo de la muestra derecha"),
        ("left_delta_rad", bracket.left_delta_rad, "rad", "Ángulo del rotor en la muestra izquierda"),
        ("right_delta_rad", bracket.right_delta_rad, "rad", "Ángulo del rotor en la muestra derecha"),
        (
            "left_omega_dev_pu",
            bracket.left_omega_dev_pu,
            "pu",
            "Desviación de velocidad en la muestra izquierda",
        ),
        (
            "right_omega_dev_pu",
            bracket.right_omega_dev_pu,
            "pu",
            "Desviación de velocidad en la muestra derecha",
        ),
    )
    return tuple(
        ExplanationEvidence(
            key=f"{prefix}_{key}",
            value=value,
            unit=unit,
            statement=f"{statement} del intervalo de evento.",
        )
        for key, value, unit, statement in values
    )


def _indeterminate_summary(reason: FirstSwingReason) -> str:
    if reason is FirstSwingReason.NO_POSITIVE_EXCURSION:
        detail = (
            (
                "no hubo una excursión con desviación de velocidad positiva en las muestras "
                "posdespeje examinadas"
            )
        )
    elif reason is FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT:
        detail = (
            (
                "el horizonte muestreado terminó antes de observar una reversión o un cruce "
                "del equilibrio inestable"
            )
        )
    else:
        detail = (
            (
                "las muestras no establecen si ocurrió primero la reversión o el cruce del "
                "equilibrio inestable"
            )
        )
    return (
        f"La primera oscilación muestreada del modelo clásico SMIB sigue siendo no concluyente porque {detail}. Se conserva ese resultado científico."
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
            statement="Desviación de velocidad muestreada al inicio de la falla.",
        ),
        ExplanationEvidence(
            key="clearing_omega_dev_pu",
            value=clearing_speed_pu,
            unit="pu",
            statement="Desviación de velocidad muestreada en el despeje.",
        ),
        ExplanationEvidence(
            key="fault_interval_speed_increased",
            value=speed_increased,
            statement=(
                "Indica si la desviación de velocidad aumentó entre el inicio de falla y el despeje."
            ),
        ),
    )
    clause = (
        (
            " Durante el intervalo de falla modelado aumentó la desviación de velocidad "
            "muestreada, lo que aporta evidencia de aceleración neta del rotor a lo largo de "
            "ese intervalo. Según la ecuación de oscilación, este cambio acumula el efecto "
            "del balance de potencia neto; no afirma que ese balance fuera positivo en cada "
            "instante."
        )
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
