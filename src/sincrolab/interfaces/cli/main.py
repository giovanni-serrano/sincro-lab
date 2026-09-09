"""Minimal stdlib CLI over the portable SincroLab application facade."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from sincrolab.application.portable import (
    GuidedAttemptRequest,
    GuidedAttemptResultDTO,
    GuidedCaseDTO,
    GuidedHintsDTO,
    ParameterValueDTO,
    PedagogicalSolutionDTO,
    QuestionAnswerDTO,
    ReferenceCaseDTO,
    ReferenceCaseResultDTO,
    TrajectoryDTO,
    dumps_portable,
    get_capabilities,
    get_learning_content,
    get_guided_case,
    get_guided_hints,
    get_guided_solution,
    get_reference_case,
    list_guided_cases,
    list_reference_cases,
    reproduce_reference_case,
    run_guided_attempt,
    trajectory_to_csv,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the deterministic command tree used by the console entry point."""
    parser = argparse.ArgumentParser(
        prog="sincrolab",
        description=(
            "Interfaz científica y de aprendizaje guiado del modelo clásico SMIB."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    capabilities = commands.add_parser(
        "capabilities", help="Mostrar capacidades de la API portable."
    )
    _add_json_flag(capabilities)

    guided = commands.add_parser("guided", help="Explorar los casos guiados.")
    guided_commands = guided.add_subparsers(dest="guided_command", required=True)
    guided_list = guided_commands.add_parser("list", help="Listar los casos guiados.")
    _add_json_flag(guided_list)
    guided_show = guided_commands.add_parser("show", help="Consultar un caso guiado.")
    guided_show.add_argument("case_id")
    _add_json_flag(guided_show)
    guided_hints = guided_commands.add_parser(
        "hints", help="Revelar pistas progresivas."
    )
    guided_hints.add_argument("case_id")
    guided_hints.add_argument("--count", type=int, required=True)
    _add_json_flag(guided_hints)
    guided_solution = guided_commands.add_parser(
        "solution", help="Mostrar explícitamente una solución pedagógica posible."
    )
    guided_solution.add_argument("case_id")
    _add_json_flag(guided_solution)
    guided_run = guided_commands.add_parser(
        "run", help="Ejecutar un intento guiado después de registrar una predicción."
    )
    guided_run.add_argument("case_id")
    guided_run.add_argument("--prediction", required=True)
    guided_run.add_argument(
        "--set",
        dest="changes",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Aplicar un cambio permitido de parámetro; puede repetirse.",
    )
    guided_run.add_argument("--hints", type=int, default=0)
    guided_run.add_argument("--reveal-solution", action="store_true")
    guided_run.add_argument(
        "--pre-answer",
        action="append",
        default=None,
        metavar="QUESTION=OPTION",
    )
    guided_run.add_argument(
        "--post-answer",
        action="append",
        default=None,
        metavar="QUESTION=OPTION",
    )
    _add_output_options(guided_run)

    reference = commands.add_parser(
        "reference", help="Consultar o reproducir referencias científicas técnicas."
    )
    reference_commands = reference.add_subparsers(
        dest="reference_command", required=True
    )
    reference_list = reference_commands.add_parser(
        "list", help="Listar los casos de referencia científica."
    )
    _add_json_flag(reference_list)
    reference_show = reference_commands.add_parser(
        "show", help="Consultar un caso de referencia científica."
    )
    reference_show.add_argument("case_id")
    _add_json_flag(reference_show)
    reference_run = reference_commands.add_parser(
        "run", help="Recalcular una referencia compatible mediante el núcleo."
    )
    reference_run.add_argument("case_id")
    reference_run.add_argument(
        "--dt-s",
        type=float,
        default=None,
        help="Resolución de la referencia adversarial, en segundos.",
    )
    _add_output_options(reference_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI, translating expected input errors to exit code 2."""
    # Portable text contains Unicode symbols; pipes must be UTF-8 on Windows too.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = _dispatch(args)
        if getattr(args, "json_output", None):
            _write_text(Path(args.json_output), dumps_portable(result))
        if getattr(args, "csv_output", None):
            _write_text(Path(args.csv_output), trajectory_to_csv(_trajectory(result)))
        _emit_result(result, as_json=args.json)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _dispatch(args: argparse.Namespace) -> object:
    if args.command == "capabilities":
        return get_capabilities()
    if args.command == "guided":
        if args.guided_command == "list":
            return list_guided_cases()
        if args.guided_command == "show":
            return get_guided_case(args.case_id)
        if args.guided_command == "hints":
            return get_guided_hints(args.case_id, args.count)
        if args.guided_command == "solution":
            return get_guided_solution(args.case_id)
        if args.guided_command == "run":
            request = GuidedAttemptRequest(
                case_id=args.case_id,
                prediction=args.prediction,
                changes=tuple(_parse_changes(args.changes)),
                hints_revealed=args.hints,
                reveal_solution=args.reveal_solution,
                pre_answers=_parse_answers(args.pre_answer),
                post_answers=_parse_answers(args.post_answer),
            )
            return run_guided_attempt(request)
    if args.command == "reference":
        if args.reference_command == "list":
            return list_reference_cases()
        if args.reference_command == "show":
            return get_reference_case(args.case_id)
        if args.reference_command == "run":
            return reproduce_reference_case(args.case_id, dt_s=args.dt_s)
    raise RuntimeError("unreachable CLI command")


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Mostrar la salida técnica JSON.")


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    _add_json_flag(parser)
    parser.add_argument("--json-output", metavar="PATH")
    parser.add_argument("--csv-output", metavar="PATH")


def _parse_changes(values: Sequence[str]) -> tuple[ParameterValueDTO, ...]:
    return tuple(
        ParameterValueDTO(key=key, value=_parse_float(key, value))
        for key, value in (_split_assignment(item) for item in values)
    )


def _parse_answers(values: Sequence[str] | None) -> tuple[QuestionAnswerDTO, ...] | None:
    if values is None:
        return None
    return tuple(
        QuestionAnswerDTO(question_id=question, option_id=option)
        for question, option in (_split_assignment(item) for item in values)
    )


def _split_assignment(value: str) -> tuple[str, str]:
    key, separator, item_value = value.partition("=")
    if not separator or not key or not item_value:
        raise ValueError(f"expected KEY=VALUE, got {value!r}")
    return key, item_value


def _parse_float(key: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got {value!r}") from exc


def _emit_result(result: object, *, as_json: bool) -> None:
    if as_json:
        print(dumps_portable(result), end="")
        return
    if isinstance(result, tuple):
        for item in result:
            print(_summary_line(item))
        return
    print(_summary_line(result))


def _meaning_label(key: str) -> str:
    return next(item.label for item in get_learning_content().meanings if item.key == key)


def _quantity_label(key: str) -> str:
    return next(item.label for item in get_learning_content().quantities if item.key == key)


def _summary_line(value: object) -> str:
    if isinstance(value, GuidedCaseDTO):
        editable = ", ".join(
            f"{item.label}=[{item.minimum}, {item.maximum}] {item.unit}"
            for item in value.editable_parameters
        )
        return (
            f"{value.case_id}: {value.title}\n"
            f"Objetivo: {value.learning_objective}\n"
            f"Predicción: {value.prediction_prompt}\n"
            f"Parámetros editables: {editable}"
        )
    case_id = getattr(value, "case_id", None)
    title = getattr(value, "title", None)
    if case_id and title:
        return f"{case_id}: {title}"
    if isinstance(value, GuidedHintsDTO):
        lines = [f"{value.case_id}: {len(value.hints)} pista(s) revelada(s)"]
        lines.extend(
            f"Pista {index}: {hint}"
            for index, hint in enumerate(value.hints, start=1)
        )
        return "\n".join(lines)
    if isinstance(value, PedagogicalSolutionDTO):
        settings = ", ".join(
            f"{_quantity_label(item.key)}={item.value} {item.unit}" for item in value.settings
        )
        return (
            f"{value.case_id}: una solución pedagógica posible\n"
            f"Configuración: {settings}\n"
            f"Explicación: {value.explanation}\n"
            f"Limitación: {value.limitation}"
        )
    if isinstance(value, GuidedAttemptResultDTO):
        result = value.attempted_evaluation.first_swing
        assessment = value.local_assessment
        score = (
            "no realizada"
            if not assessment.assessed
            else f"{assessment.pre_score.correct}/{assessment.pre_score.total} -> "
            f"{assessment.post_score.correct}/{assessment.post_score.total}"
        )
        return (
            f"{value.case_id}: {_meaning_label(result.status)} · {_meaning_label(result.reason)}\n"
            f"Objetivo alcanzado: {'sí' if value.goal_evaluation.achieved else 'no'} · Autoevaluación: {score}\n"
            f"Explicación final: {value.debrief_summary}"
        )
    if isinstance(value, ReferenceCaseResultDTO):
        first_swing = value.evaluation.first_swing
        return (
            f"{value.case_id}: {_meaning_label(first_swing.status)} · "
            f"{_meaning_label(first_swing.reason)}\n"
            f"Observaciones verificadas: {len(value.observations)} · "
            "Todas las observaciones reportadas coinciden: "
            f"{'sí' if value.all_reported_observations_match_expected else 'no'}"
        )
    if isinstance(value, ReferenceCaseDTO):
        evidence = ", ".join(
            item.value for item in value.evidence_types_present
        )
        return (
            f"{value.case_id}: {value.purpose}\n"
            f"Tipos de evidencia (identificadores técnicos): {evidence}\n"
            f"Alcance técnico de reproducción: {value.runtime_reproduction_scope}\n"
            f"Fuente canónica: {value.canonical_source}\n"
            f"Limitación: {value.limitation}"
        )
    case_id = getattr(value, "case_id", None)
    if case_id:
        purpose = getattr(value, "purpose", "")
        return f"{case_id}: {purpose}"
    data = value.to_dict()  # type: ignore[attr-defined]
    return " ".join(f"{key}={item}" for key, item in data.items())


def _trajectory(result: object) -> TrajectoryDTO:
    if isinstance(result, GuidedAttemptResultDTO):
        return result.attempted_evaluation.trajectory
    if isinstance(result, ReferenceCaseResultDTO):
        return result.evaluation.trajectory
    raise ValueError("CSV export is available only for executed trajectory results")


def _write_text(path: Path, content: str) -> None:
    if not path.name:
        raise ValueError("output path must name a file")
    path.write_text(content, encoding="utf-8", newline="")


__all__ = ["build_parser", "main"]
