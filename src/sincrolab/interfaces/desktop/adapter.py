"""The single desktop import boundary to application.portable.

Requests/results remain portable DTOs. H26 creates PreparedGuidedAttempt and
AttemptRecord inside H25; desktop neither reconstructs nor bypasses them.
All history is in memory, without identifiers, timestamps or external IO.
"""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from collections.abc import Callable, Mapping
from math import isfinite

import sincrolab.application.portable as portable
from sincrolab.interfaces.desktop.presentation import (
    CasePreview, CaseView, Curve, InputField, QuestionView, ResultView, number,
)


def _preview(case: portable.GuidedCaseSummaryDTO | portable.GuidedCaseDTO) -> CasePreview:
    return CasePreview(
        case.case_id, case.title, case.kind, case.learning_objective, case.difficulty,
    )


def _config_rows(config: portable.SimulationConfigDTO) -> tuple[tuple[str, str], ...]:
    rows = []
    for group, value in config.to_dict().items():
        if group == "schema_version":
            continue
        if isinstance(value, dict):
            rows.extend((key, number(item)) for key, item in value.items()
                        if key != "schema_version")
        else:
            rows.append((group, number(value)))
    return tuple(rows)


def _explanation(value: portable.ExplanationDTO) -> str:
    """Render H24 text/evidence verbatim; do not interpret its status."""
    lines = [value.title, value.summary, ""]
    lines.extend(
        f"{item.statement}\n{item.key}: {number(item.value)} {item.unit or ''}"
        for item in value.evidence
    )
    lines.extend(("", *value.limitations))
    return "\n\n".join(lines)


def _curve(name: str, evaluation: portable.ClearingTimeEvaluationDTO) -> Curve:
    trajectory = evaluation.trajectory
    return Curve(name, trajectory.time_s, trajectory.delta_rad, trajectory.omega_dev_pu)


def _assessment(result: portable.GuidedAttemptResultDTO) -> str:
    score = result.local_assessment
    if not score.assessed:
        return "Autoevaluación no realizada. Sin respuestas no se asigna una puntuación."
    return (
        f"Pre: {score.pre_score.correct}/{score.pre_score.total} · "
        f"Post: {score.post_score.correct}/{score.post_score.total} · "
        f"Cambio local: {score.local_delta}\n{score.limitation}"
    )


def _result_view(result: portable.GuidedAttemptResultDTO) -> ResultView:
    comparison = result.scientific_comparison
    rows = (
        ("Estado", comparison.baseline_status, comparison.attempted_status),
        ("Razón", comparison.baseline_reason, comparison.attempted_reason),
        ("Máximo delta_rad", number(comparison.baseline_max_delta_rad),
         number(comparison.attempted_max_delta_rad)),
        ("Máximo |omega_dev_pu|", number(comparison.baseline_max_abs_omega_dev_pu),
         number(comparison.attempted_max_abs_omega_dev_pu)),
    )
    clearing = ""
    if result.critical_clearing_bracket is not None:
        bracket = result.critical_clearing_bracket
        clearing = "\n".join(
            f"{key}: {number(value)}" for key, value in bracket.to_dict().items()
            if key != "schema_version"
        )
        if result.critical_clearing_explanation is not None:
            clearing += "\n\n" + _explanation(result.critical_clearing_explanation)
    observed = result.attempted_evaluation
    return ResultView(
        status=observed.first_swing.status,
        reason=observed.first_swing.reason,
        prediction=result.prediction,
        configuration=_config_rows(result.attempted_config),
        curves=(_curve("Baseline", result.baseline_evaluation), _curve("Intento", observed)),
        comparison=rows,
        changes=tuple(
            (item.key, number(item.baseline_value), number(item.attempted_value), item.unit)
            for item in result.changed_parameters
        ),
        explanation=_explanation(observed.explanation),
        assessment=_assessment(result),
        debrief="\n\n".join((
            result.debrief_summary, result.goal_evaluation.evidence,
            *result.debrief_limitations,
        )),
        clearing=clearing,
    )


class DesktopController:
    """Own one explicit session; workers execute immutable request snapshots."""

    def __init__(self) -> None:
        self.catalog = tuple(_preview(case) for case in portable.list_guided_cases())
        self.case: portable.GuidedCaseDTO | None = None
        self.phase = "Observar"
        self.prediction: str | None = None
        self.changes: dict[str, float] = {}
        self.hints: tuple[str, ...] = ()
        self.solution: portable.PedagogicalSolutionDTO | None = None
        self.pre_answers: tuple[portable.QuestionAnswerDTO, ...] | None = None
        self.request: portable.GuidedAttemptRequest | None = None
        self.completed_request: portable.GuidedAttemptRequest | None = None
        self.completed_pre_answers: tuple[portable.QuestionAnswerDTO, ...] | None = None
        self.result: portable.GuidedAttemptResultDTO | None = None
        self.history: list[portable.GuidedAttemptResultDTO] = []
        self.free_config: portable.SimulationConfigDTO | None = None
        self.free_result: portable.ClearingTimeEvaluationDTO | None = None

    def select_case(self, case_id: str) -> CaseView:
        case = portable.get_guided_case(case_id)
        if self.case is None or self.case.case_id != case_id:
            self.case = case
            self.phase = "Observar"
            self.prediction = None
            self.changes = {}
            self.hints = ()
            self.solution = None
            self.pre_answers = None
            self.request = None
            self.completed_request = None
            self.completed_pre_answers = None
            self.result = None
            self.history = []
        return self.case_view()

    def case_view(self) -> CaseView:
        if self.case is None:
            raise ValueError("No hay un caso seleccionado.")
        case = self.case
        return CaseView(
            _preview(case), case.context, _config_rows(case.baseline_config),
            case.prediction_prompt, case.prediction_options,
            tuple(InputField(
                item.key, item.label, self.changes.get(item.key, item.baseline_value),
                item.unit, item.minimum, item.maximum,
            ) for item in case.editable_parameters),
            tuple(QuestionView(
                item.question_id, item.prompt,
                tuple((option.option_id, option.text) for option in item.options),
            ) for item in case.conceptual_questions),
            case.hints_available, case.has_pedagogical_solution, case.provenance,
        )

    def go_to(self, phase: str) -> None:
        """Gate display phases without assigning a scientific meaning to them."""
        self.case_view()
        if phase in ("Observar", "Predecir"):
            self.phase = phase
        elif phase in ("Simular", "Intervenir", "Comparar", "Explicar"):
            if self.result is None:
                raise ValueError("Primero registra una predicción y ejecuta el caso.")
            self.phase = phase
        else:
            raise ValueError(f"Fase desconocida: {phase}")

    def set_changes(self, values: Mapping[str, str | float]) -> None:
        fields = {item.key: item for item in self.case_view().fields}
        if set(values) - fields.keys():
            raise ValueError("El cambio contiene parámetros no editables del caso.")
        parsed = {key: self._number(key, value) for key, value in values.items()}
        for key, value in parsed.items():
            field = fields[key]
            if not field.minimum <= value <= field.maximum:
                raise ValueError(
                    f"{key} debe estar entre {field.minimum} y {field.maximum} {field.unit}."
                )
        self.changes = parsed
        self.prediction = None
        self.pre_answers = None
        self.request = None
        self.phase = "Predecir"

    @staticmethod
    def _number(key: str, value: str | float) -> float:
        try:
            parsed = float(value)
        except (ValueError, TypeError) as error:
            raise ValueError(f"{key}: introduce un número válido.") from error
        if isinstance(value, bool) or not isfinite(parsed):
            raise ValueError(f"{key}: introduce un número finito.")
        return parsed

    def _answers(self, values: Mapping[str, str]) -> tuple[portable.QuestionAnswerDTO, ...]:
        questions = self.case_view().questions
        if set(values) != {question.key for question in questions}:
            raise ValueError("Completa todas las preguntas o desactiva la autoevaluación.")
        for question in questions:
            if values[question.key] not in dict(question.options):
                raise ValueError("Hay una pregunta sin responder; no se ha puntuado.")
        return tuple(portable.QuestionAnswerDTO(q.key, values[q.key]) for q in questions)

    def prepare(self, prediction: str | None, pre_answers: Mapping[str, str] | None = None) -> None:
        case = self.case_view()
        if prediction not in case.prediction_options:
            raise ValueError("Selecciona una predicción antes de simular.")
        pre = None if pre_answers is None else self._answers(pre_answers)
        self.prediction = prediction
        self.pre_answers = pre
        # H26's atomic workflow accepts pre/post only as a complete pair.
        # The first execution has no assessment; assessment_job replays this
        # exact request after post answers exist, replacing the retained record.
        self.request = portable.GuidedAttemptRequest(
            case_id=case.preview.case_id, prediction=prediction,
            changes=tuple(portable.ParameterValueDTO(k, v) for k, v in self.changes.items()),
            hints_revealed=len(self.hints), reveal_solution=self.solution is not None,
        )

    def guided_job(self) -> Callable[[], portable.GuidedAttemptResultDTO]:
        if self.request is None:
            raise ValueError("Se requiere una predicción preparada.")
        return partial(portable.run_guided_attempt, self.request)

    def accept_guided(self, result: portable.GuidedAttemptResultDTO, *, assessment: bool = False) -> None:
        expected = self.completed_request if assessment else self.request
        if expected is None or result.case_id != expected.case_id:
            raise RuntimeError("Portable result does not belong to the active request.")
        self.result = result
        if assessment:
            self.history[-1] = result
            self.phase = "Explicar"
        else:
            self.completed_request = self.request
            self.completed_pre_answers = self.pre_answers
            self.history.append(result)
            self.phase = "Simular" if len(self.history) == 1 else "Comparar"

    def assessment_job(self, post_answers: Mapping[str, str]) -> Callable[[], portable.GuidedAttemptResultDTO]:
        if (self.result is None or self.completed_request is None
                or self.completed_pre_answers is None):
            raise ValueError("Esta ejecución no inició una autoevaluación pre/post.")
        request = replace(
            self.completed_request, pre_answers=self.completed_pre_answers,
            post_answers=self._answers(post_answers),
        )
        return partial(portable.run_guided_attempt, request)

    def reveal_hint(self) -> None:
        case = self.case_view()
        count = min(len(self.hints) + 1, case.hints_available)
        self.hints = portable.get_guided_hints(case.preview.case_id, count).hints

    def reveal_solution(self) -> None:
        case = self.case_view()
        solution = portable.get_guided_solution(case.preview.case_id)
        self.set_changes({item.key: item.value for item in solution.settings})
        self.solution = solution

    def solution_text(self) -> str:
        if self.solution is None:
            return ""
        return "\n\n".join((self.solution.explanation, self.solution.limitation))

    def result_view(self) -> ResultView | None:
        return None if self.result is None else _result_view(self.result)

    def history_rows(self) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            (str(index), result.prediction, result.attempted_evaluation.first_swing.status,
             ", ".join(f"{item.key}: {number(item.baseline_value)} → "
                       f"{number(item.attempted_value)} {item.unit}"
                       for item in result.changed_parameters) or "Sin cambios")
            for index, result in enumerate(self.history, start=1)
        )

    def free_fields(self) -> tuple[InputField, ...]:
        if self.free_config is None:
            if not self.catalog:
                raise ValueError("No hay una configuración pública disponible.")
            self.free_config = portable.get_guided_case(self.catalog[0].case_id).baseline_config
        # Offer a small subset; all other inputs, including the explicit initial
        # state, stay visible and are retained from the selected public baseline.
        config = self.free_config
        return (
            InputField("H_s", "H_s · inercia", config.parameters.H_s, "s"),
            InputField("t_clear_s", "t_clear_s · despeje", config.network.t_clear_s, "s"),
            InputField("t_end_s", "t_end_s · horizonte", config.t_end_s, "s"),
            InputField("dt_s", "dt_s · paso temporal", config.dt_s, "s"),
        )

    def free_configuration(self) -> tuple[tuple[str, str], ...]:
        self.free_fields()
        return _config_rows(self.free_config)

    def prepare_free(self, values: Mapping[str, str | float]) -> Callable[[], portable.ClearingTimeEvaluationDTO]:
        fields = self.free_fields()
        if set(values) != {item.key for item in fields}:
            raise ValueError("Completa los cuatro parámetros de Modo libre.")
        parsed = {key: self._number(key, value) for key, value in values.items()}
        config = replace(
            self.free_config,
            parameters=replace(self.free_config.parameters, H_s=parsed["H_s"]),
            network=replace(self.free_config.network, t_clear_s=parsed["t_clear_s"]),
            t_end_s=parsed["t_end_s"], dt_s=parsed["dt_s"],
        )
        # Domain validation and all time-grid decisions remain in portable.
        return partial(portable.evaluate_transient, config)

    def accept_free(self, result: portable.ClearingTimeEvaluationDTO) -> None:
        self.free_config = result.configuration
        self.free_result = result

    def free_result_view(self) -> ResultView | None:
        value = self.free_result
        if value is None:
            return None
        return ResultView(
            value.first_swing.status, value.first_swing.reason, "",
            _config_rows(value.configuration), (_curve("Ejecución", value),),
            (), (), _explanation(value.explanation), "", "", "",
        )
