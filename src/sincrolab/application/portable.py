"""Portable application facade for CLI, desktop, and web interfaces.

The DTOs in this module contain only JSON-compatible scalar values, tuples,
and other portable DTOs. Scientific work is delegated to the existing H18-H25
application and analysis paths; this module only adapts inputs and outputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from enum import Enum
from functools import lru_cache
from importlib.resources import files
import csv
import io
import json
from math import isfinite
from typing import Any, ClassVar

import numpy as np

from sincrolab.application import learning_content
from sincrolab import __version__
from sincrolab.analysis import FirstSwingEventBracket
from sincrolab.application.guided_learning import (
    AttemptRecord,
    ConceptQuestion,
    GuidedCase,
    GuidedSimulationConfig,
    PedagogicalSolution,
    QuestionAnswer,
    default_guided_cases,
    prepare_guided_attempt,
    reveal_progressive_hints,
    run_guided_attempt as run_h25_guided_attempt,
)
from sincrolab.application.learning import (
    PedagogicalExplanation,
    explain_first_swing,
)
from sincrolab.application.clearing_time import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
    evaluate_smib_clearing_time,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


PORTABLE_SCHEMA_VERSION = 1
PORTABLE_API_VERSION = "1.0"
RELEASE_TARGET = "v0.1.0-core"


class ReferenceEvidenceType(Enum):
    """H23 evidence taxonomy retained by portable reference outputs."""

    ANALYTIC_ORACLE = "ANALYTIC_ORACLE"
    EXTERNAL_NUMERICAL_ORACLE = "EXTERNAL_NUMERICAL_ORACLE"
    CROSS_CHECKED_EVIDENCE = "CROSS_CHECKED_EVIDENCE"
    ACCEPTED_REGRESSION = "ACCEPTED_REGRESSION"


@dataclass(frozen=True)
class _PortableDTO:
    """Base for the closed set of deliberately serializable H26 DTOs."""

    schema_version: ClassVar[int] = PORTABLE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            **{field.name: _encode_portable(getattr(self, field.name)) for field in fields(self)},
        }


@dataclass(frozen=True)
class PortableCapabilities(_PortableDTO):
    package_version: str
    release_target: str
    portable_api_version: str
    guided_operations: tuple[str, ...]
    scientific_operations: tuple[str, ...]
    reference_operations: tuple[str, ...]
    export_formats: tuple[str, ...]
    trajectory_fields: tuple[str, ...]


@dataclass(frozen=True)
class LearningContentDTO(_PortableDTO):
    """Read-only product semantics, separate from scientific request schemas."""

    topics: tuple[learning_content.TheoryTopic, ...]
    quantities: tuple[learning_content.DisplayQuantity, ...]
    glossary: tuple[learning_content.TermDefinition, ...]
    meanings: tuple[learning_content.TermDefinition, ...]
    cases: tuple[learning_content.CaseGuidance, ...]
    learning_path: tuple[learning_content.LearningStep, ...]
    block_labels: tuple[learning_content.TermDefinition, ...]


def get_learning_content() -> LearningContentDTO:
    """Expose shared Spanish content without executing or revealing a solution."""
    return LearningContentDTO(
        learning_content.TOPICS, learning_content.QUANTITIES,
        learning_content.GLOSSARY, learning_content.MEANINGS,
        learning_content.CASE_GUIDANCE, learning_content.LEARNING_PATH,
        learning_content.BLOCK_LABELS,
    )


@dataclass(frozen=True)
class SMIBParametersDTO(_PortableDTO):
    H_s: float
    D_pu: float
    f_base_hz: float
    Pm_pu: float


@dataclass(frozen=True)
class SMIBInitialStateDTO(_PortableDTO):
    delta_rad: float
    omega_dev_pu: float


@dataclass(frozen=True)
class SMIBTransientNetworkDTO(_PortableDTO):
    Pmax_prefault_pu: float
    Pmax_fault_pu: float
    Pmax_postfault_pu: float
    t_fault_s: float
    t_clear_s: float


@dataclass(frozen=True)
class SimulationConfigDTO(_PortableDTO):
    parameters: SMIBParametersDTO
    initial_state: SMIBInitialStateDTO
    network: SMIBTransientNetworkDTO
    t_start_s: float
    t_end_s: float
    dt_s: float


@dataclass(frozen=True)
class TrajectoryDTO(_PortableDTO):
    """Portable trajectory with explicit units in stable field names."""

    time_s: tuple[float, ...]
    delta_rad: tuple[float, ...]
    omega_dev_pu: tuple[float, ...]


@dataclass(frozen=True)
class EventBracketDTO(_PortableDTO):
    left_index: int
    right_index: int
    left_time_s: float
    right_time_s: float
    left_delta_rad: float
    right_delta_rad: float
    left_omega_dev_pu: float
    right_omega_dev_pu: float


@dataclass(frozen=True)
class FirstSwingDTO(_PortableDTO):
    status: str
    reason: str
    delta_stable_post_rad: float
    delta_unstable_post_rad: float
    reversal_bracket: EventBracketDTO | None
    crossing_bracket: EventBracketDTO | None


@dataclass(frozen=True)
class ExplanationEvidenceDTO(_PortableDTO):
    key: str
    value: bool | float | int | str
    statement: str
    unit: str | None


@dataclass(frozen=True)
class ExplanationDTO(_PortableDTO):
    kind: str
    title: str
    summary: str
    evidence: tuple[ExplanationEvidenceDTO, ...]
    limitations: tuple[str, ...]
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class ClearingTimeBracketDTO(_PortableDTO):
    """Portable H19 bracket; no midpoint or exact-CCT field is exposed."""

    stable_t_clear_s: float
    stable_status: str
    stable_reason: str
    unstable_t_clear_s: float
    unstable_status: str
    unstable_reason: str
    bracket_width_s: float
    time_tolerance_s: float
    time_tolerance_meaning: str
    dt_s: float
    iterations: int


@dataclass(frozen=True)
class ClearingTimeEvaluationDTO(_PortableDTO):
    configuration: SimulationConfigDTO
    trajectory: TrajectoryDTO
    first_swing: FirstSwingDTO
    explanation: ExplanationDTO


@dataclass(frozen=True)
class EditableParameterDTO(_PortableDTO):
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    baseline_value: float


@dataclass(frozen=True)
class ConceptOptionDTO(_PortableDTO):
    option_id: str
    text: str


@dataclass(frozen=True)
class ConceptQuestionDTO(_PortableDTO):
    question_id: str
    prompt: str
    options: tuple[ConceptOptionDTO, ...]


@dataclass(frozen=True)
class GuidedCaseSummaryDTO(_PortableDTO):
    case_id: str
    kind: str
    title: str
    difficulty: str
    learning_objective: str


@dataclass(frozen=True)
class GuidedCaseDTO(_PortableDTO):
    case_id: str
    kind: str
    title: str
    context: str
    learning_objective: str
    difficulty: str
    baseline_config: SimulationConfigDTO
    goal_kind: str
    target_status: str | None
    prediction_prompt: str
    prediction_options: tuple[str, ...]
    editable_parameters: tuple[EditableParameterDTO, ...]
    hints_available: int
    has_pedagogical_solution: bool
    conceptual_questions: tuple[ConceptQuestionDTO, ...]
    debrief_concepts: tuple[str, ...]
    provenance: str


@dataclass(frozen=True)
class GuidedHintsDTO(_PortableDTO):
    case_id: str
    requested_count: int
    hints: tuple[str, ...]


@dataclass(frozen=True)
class SolutionSettingDTO(_PortableDTO):
    key: str
    value: float
    unit: str


@dataclass(frozen=True)
class PedagogicalSolutionDTO(_PortableDTO):
    case_id: str
    settings: tuple[SolutionSettingDTO, ...]
    explanation: str
    limitation: str


@dataclass(frozen=True)
class ParameterValueDTO(_PortableDTO):
    key: str
    value: float


@dataclass(frozen=True)
class QuestionAnswerDTO(_PortableDTO):
    question_id: str
    option_id: str


@dataclass(frozen=True)
class GuidedAttemptRequest(_PortableDTO):
    case_id: str
    prediction: str
    changes: tuple[ParameterValueDTO, ...] = ()
    hints_revealed: int = 0
    reveal_solution: bool = False
    pre_answers: tuple[QuestionAnswerDTO, ...] | None = None
    post_answers: tuple[QuestionAnswerDTO, ...] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> GuidedAttemptRequest:
        """Build a validated request from a JSON-decoded mapping."""
        if not isinstance(value, Mapping):
            raise TypeError("guided attempt request must be a mapping")
        allowed = {
            "schema_version",
            "case_id",
            "prediction",
            "changes",
            "hints_revealed",
            "reveal_solution",
            "pre_answers",
            "post_answers",
        }
        unexpected = set(value) - allowed
        if unexpected:
            raise ValueError(
                "guided attempt request contains unknown fields: "
                + ", ".join(sorted(unexpected))
            )
        if "schema_version" not in value:
            raise ValueError("guided attempt request requires schema_version")
        _validate_schema_version(value)
        case_id = value.get("case_id")
        prediction = value.get("prediction")
        if not isinstance(case_id, str) or not isinstance(prediction, str):
            raise TypeError("case_id and prediction must be strings")
        changes = _parse_parameter_values(value.get("changes", ()))
        hints_revealed = value.get("hints_revealed", 0)
        reveal_solution = value.get("reveal_solution", False)
        if isinstance(hints_revealed, bool) or not isinstance(hints_revealed, int):
            raise TypeError("hints_revealed must be an integer")
        if not isinstance(reveal_solution, bool):
            raise TypeError("reveal_solution must be boolean")
        return cls(
            case_id=case_id,
            prediction=prediction,
            changes=changes,
            hints_revealed=hints_revealed,
            reveal_solution=reveal_solution,
            pre_answers=_parse_answers(value.get("pre_answers")),
            post_answers=_parse_answers(value.get("post_answers")),
        )


@dataclass(frozen=True)
class ParameterChangeDTO(_PortableDTO):
    key: str
    baseline_value: float
    attempted_value: float
    unit: str


@dataclass(frozen=True)
class ScientificComparisonDTO(_PortableDTO):
    baseline_status: str
    attempted_status: str
    baseline_reason: str
    attempted_reason: str
    baseline_max_delta_rad: float
    attempted_max_delta_rad: float
    baseline_max_abs_omega_dev_pu: float
    attempted_max_abs_omega_dev_pu: float


@dataclass(frozen=True)
class GoalEvaluationDTO(_PortableDTO):
    achieved: bool
    kind: str
    observed_status: str
    target_status: str | None
    evidence: str


@dataclass(frozen=True)
class ConceptScoreDTO(_PortableDTO):
    correct: int
    total: int


@dataclass(frozen=True)
class LocalAssessmentDTO(_PortableDTO):
    assessed: bool
    pre_score: ConceptScoreDTO | None
    post_score: ConceptScoreDTO | None
    local_delta: int | None
    limitation: str | None


@dataclass(frozen=True)
class GuidedAttemptResultDTO(_PortableDTO):
    case_id: str
    prediction: str
    baseline_config: SimulationConfigDTO
    attempted_config: SimulationConfigDTO
    changed_parameters: tuple[ParameterChangeDTO, ...]
    baseline_evaluation: ClearingTimeEvaluationDTO
    attempted_evaluation: ClearingTimeEvaluationDTO
    scientific_comparison: ScientificComparisonDTO
    goal_evaluation: GoalEvaluationDTO
    hints_revealed: tuple[str, ...]
    solution_revealed: bool
    revealed_solution: PedagogicalSolutionDTO | None
    pre_answers: tuple[QuestionAnswerDTO, ...] | None
    post_answers: tuple[QuestionAnswerDTO, ...] | None
    local_assessment: LocalAssessmentDTO
    critical_clearing_bracket: ClearingTimeBracketDTO | None
    critical_clearing_explanation: ExplanationDTO | None
    debrief_summary: str
    debrief_limitations: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceInitialStateContractDTO(_PortableDTO):
    delta_rad_source: str
    omega_dev_pu: float


@dataclass(frozen=True)
class ReferenceCCTSearchDTO(_PortableDTO):
    stable_t_clear_s: float
    unstable_t_clear_s: float
    t_start_s: float
    t_end_s: float
    dt_s: float
    time_tolerance_s: float
    angle_tolerance_rad: float
    max_iterations: int
    tolerance_interpretation: str


@dataclass(frozen=True)
class ReferenceExternalNumericalDTO(_PortableDTO):
    solver: str
    method: str
    rtol: float
    atol: float
    usage: str


@dataclass(frozen=True)
class ReferenceExpectedObservationDTO(_PortableDTO):
    observation_id: str
    expected_field: str
    expected_value: bool | float | int | str
    comparison: str
    comparison_parameter: str | None
    comparison_value: float | None
    evidence_type: ReferenceEvidenceType
    provenance: str
    dt_s: float | None


@dataclass(frozen=True)
class ReferenceObservationResultDTO(_PortableDTO):
    expected: ReferenceExpectedObservationDTO
    observed_value: bool | float | int | str
    matches_expected: bool


@dataclass(frozen=True)
class ReferenceCaseSummaryDTO(_PortableDTO):
    case_id: str
    purpose: str
    evidence_types_present: tuple[ReferenceEvidenceType, ...]
    runtime_reproduction_scope: str
    canonical_source: str
    limitation: str


@dataclass(frozen=True)
class ReferenceCaseDTO(_PortableDTO):
    case_id: str
    purpose: str
    evidence_types_present: tuple[ReferenceEvidenceType, ...]
    runtime_reproduction_scope: str
    input_case_file: str | None
    configuration: SimulationConfigDTO
    initial_state_contract: ReferenceInitialStateContractDTO
    expected_observations: tuple[ReferenceExpectedObservationDTO, ...]
    cct_search: ReferenceCCTSearchDTO | None
    external_reference: ReferenceExternalNumericalDTO | None
    collection_provenance: str
    canonical_source: str
    projection_source: str
    limitation: str


@dataclass(frozen=True)
class ReferenceCaseResultDTO(_PortableDTO):
    case_id: str
    verification_scope: str
    observations: tuple[ReferenceObservationResultDTO, ...]
    all_reported_observations_match_expected: bool
    evaluation: ClearingTimeEvaluationDTO
    canonical_source: str
    input_case_file: str
    limitation: str


@dataclass(frozen=True)
class _ReferenceDefinition:
    case_id: str
    source_case: Mapping[str, Any]
    input_case: Mapping[str, Any] | None
    config: GuidedSimulationConfig
    runtime_reproduction_scope: str



PortableOutput = (
    LearningContentDTO |
    PortableCapabilities
    | GuidedCaseSummaryDTO
    | GuidedCaseDTO
    | GuidedHintsDTO
    | PedagogicalSolutionDTO
    | GuidedAttemptRequest
    | GuidedAttemptResultDTO
    | ReferenceCaseSummaryDTO
    | ReferenceCaseDTO
    | ReferenceCaseResultDTO
    | ClearingTimeEvaluationDTO
    | TrajectoryDTO
)


def get_capabilities() -> PortableCapabilities:
    """Return stable interface-facing operations and export contracts."""
    return PortableCapabilities(
        package_version=__version__,
        release_target=RELEASE_TARGET,
        portable_api_version=PORTABLE_API_VERSION,
        guided_operations=("list", "show", "hints", "solution", "run"),
        scientific_operations=("evaluate_transient",),
        reference_operations=("list", "show", "run"),
        export_formats=("json", "csv"),
        trajectory_fields=("time_s", "delta_rad", "omega_dev_pu"),
    )


def evaluate_transient(config: SimulationConfigDTO) -> ClearingTimeEvaluationDTO:
    """Evaluate one portable transient configuration through H18 and H15."""
    if not isinstance(config, SimulationConfigDTO):
        raise TypeError("config must be a SimulationConfigDTO")
    domain_config = _config_from_dto(config)
    evaluation = evaluate_smib_clearing_time(
        domain_config.parameters,
        domain_config.initial_state,
        domain_config.network,
        t_clear_s=domain_config.network.t_clear_s,
        t_start_s=domain_config.t_start_s,
        t_end_s=domain_config.t_end_s,
        dt_s=domain_config.dt_s,
    )
    return _evaluation_dto(evaluation)


def list_guided_cases() -> tuple[GuidedCaseSummaryDTO, ...]:
    """List H25 guided cases without revealing hints, answers, or solutions."""
    return tuple(_guided_summary(case) for case in default_guided_cases())


def get_guided_case(case_id: str) -> GuidedCaseDTO:
    """Return student-facing metadata for one H25 guided case."""
    case = _find_guided_case(case_id)
    return GuidedCaseDTO(
        case_id=case.case_id,
        kind=case.kind.value,
        title=case.title,
        context=case.context,
        learning_objective=case.learning_objective,
        difficulty=case.difficulty.value,
        baseline_config=_config_dto(case.baseline_config),
        goal_kind=case.goal.kind.value,
        target_status=(case.goal.target_status.value if case.goal.target_status else None),
        prediction_prompt=case.prediction_prompt,
        prediction_options=case.prediction_options,
        editable_parameters=tuple(
            EditableParameterDTO(
                key=item.key,
                label=item.label,
                unit=item.unit,
                minimum=item.minimum,
                maximum=item.maximum,
                baseline_value=item.baseline_value,
            )
            for item in case.editable_parameters
        ),
        hints_available=len(case.hints),
        has_pedagogical_solution=case.pedagogical_solution is not None,
        conceptual_questions=tuple(
            _question_dto(question) for question in case.conceptual_questions
        ),
        debrief_concepts=tuple(concept.value for concept in case.debrief_concepts),
        provenance=case.provenance,
    )


def get_guided_hints(case_id: str, count: int) -> GuidedHintsDTO:
    """Reveal exactly the ordered H25 hint prefix requested by the caller."""
    case = _find_guided_case(case_id)
    hints = reveal_progressive_hints(case, count)
    return GuidedHintsDTO(case_id=case_id, requested_count=count, hints=hints)


def get_guided_solution(case_id: str) -> PedagogicalSolutionDTO:
    """Return one explicitly requested pedagogical solution, if available."""
    case = _find_guided_case(case_id)
    if case.pedagogical_solution is None:
        raise ValueError(f"guided case {case_id!r} has no pedagogical solution")
    return _solution_dto(case.case_id, case.pedagogical_solution)


def run_guided_attempt(request: GuidedAttemptRequest) -> GuidedAttemptResultDTO:
    """Run one portable request through H25 without duplicating its semantics."""
    if not isinstance(request, GuidedAttemptRequest):
        raise TypeError("request must be a GuidedAttemptRequest")
    case = _find_guided_case(request.case_id)
    changes = _unique_parameter_mapping(request.changes)
    prepared = prepare_guided_attempt(case, request.prediction)
    record = run_h25_guided_attempt(
        prepared,
        changes,
        hints_revealed=request.hints_revealed,
        reveal_solution=request.reveal_solution,
        pre_answers=_answers_to_domain(request.pre_answers),
        post_answers=_answers_to_domain(request.post_answers),
    )
    return _attempt_result_dto(record)


def list_reference_cases() -> tuple[ReferenceCaseSummaryDTO, ...]:
    """List H23 cases with case-level evidence sets labeled as aggregates."""
    return tuple(
        ReferenceCaseSummaryDTO(
            case_id=item.case_id,
            purpose=str(item.source_case["purpose"]),
            evidence_types_present=_evidence_types_present(item.source_case),
            runtime_reproduction_scope=item.runtime_reproduction_scope,
            canonical_source=_canonical_reference_source(),
            limitation=str(item.source_case["limitations"]),
        )
        for item in _reference_definitions()
    )


def get_reference_case(case_id: str) -> ReferenceCaseDTO:
    """Project one canonical H23 case into a traceable portable contract."""
    item = _find_reference_case(case_id)
    source_case = item.source_case
    input_case_file = source_case.get("input_case_file")
    return ReferenceCaseDTO(
        case_id=item.case_id,
        purpose=str(source_case["purpose"]),
        evidence_types_present=_evidence_types_present(source_case),
        runtime_reproduction_scope=item.runtime_reproduction_scope,
        input_case_file=str(input_case_file) if input_case_file else None,
        configuration=_config_dto(item.config),
        initial_state_contract=_initial_state_contract_dto(item),
        expected_observations=_expected_observation_dtos(source_case),
        cct_search=_cct_search_dto(source_case),
        external_reference=_external_reference_dto(source_case),
        collection_provenance=_collection_provenance(),
        canonical_source=_canonical_reference_source(),
        projection_source="sincrolab.application/_h23_reference_projection.json",
        limitation=str(source_case["limitations"]),
    )


def reproduce_reference_case(
    case_id: str,
    *,
    dt_s: float | None = None,
) -> ReferenceCaseResultDTO:
    """Recompute and verify every H23 observation reported for one execution."""
    item = _find_reference_case(case_id)
    if item.runtime_reproduction_scope == "query_only":
        raise ValueError(
            f"reference case {case_id!r} is query-only in the runtime; "
            "its granular evidence remains available through get_reference_case"
        )

    config = item.config
    expected_observations = _expected_observation_dtos(item.source_case)
    if item.runtime_reproduction_scope == "selected_time_step_classification":
        supported = tuple(
            observation.dt_s
            for observation in expected_observations
            if observation.dt_s is not None
        )
        if dt_s is None:
            choices = ", ".join(repr(value) for value in supported)
            raise ValueError(
                "dt_s is required for this reference case; "
                f"choose one of: {choices}"
            )
        selected_dt_s = _finite_float("dt_s", dt_s)
        if selected_dt_s not in supported:
            choices = ", ".join(repr(value) for value in supported)
            raise ValueError(
                f"dt_s={selected_dt_s!r} is not a retained adversarial "
                f"reference resolution; choose one of: {choices}"
            )
        config = replace(config, dt_s=selected_dt_s)
    elif dt_s is not None:
        raise ValueError("dt_s override is unavailable for this reference case")

    evaluation = evaluate_smib_clearing_time(
        config.parameters,
        config.initial_state,
        config.network,
        t_clear_s=config.network.t_clear_s,
        t_start_s=config.t_start_s,
        t_end_s=config.t_end_s,
        dt_s=config.dt_s,
    )
    if item.runtime_reproduction_scope == "all_expected_observations":
        observations = _verify_transient_reference_observations(
            expected_observations,
            evaluation,
        )
    else:
        observations = _verify_selected_classification(
            expected_observations,
            evaluation,
            dt_s=config.dt_s,
        )

    input_case_file = item.source_case.get("input_case_file")
    if not isinstance(input_case_file, str):
        raise RuntimeError("runtime-reproducible H23 case lacks input_case_file")
    return ReferenceCaseResultDTO(
        case_id=case_id,
        verification_scope=item.runtime_reproduction_scope,
        observations=observations,
        all_reported_observations_match_expected=all(
            observation.matches_expected for observation in observations
        ),
        evaluation=_evaluation_dto(evaluation),
        canonical_source=_canonical_reference_source(),
        input_case_file=input_case_file,
        limitation=str(item.source_case["limitations"]),
    )


def dumps_portable(
    value: PortableOutput | Sequence[PortableOutput],
    *,
    indent: int | None = 2,
) -> str:
    """Serialize only H26 DTOs to deterministic, standards-compliant JSON."""
    encoded = _encode_portable(value)
    return json.dumps(
        encoded,
        ensure_ascii=False,
        allow_nan=False,
        indent=indent,
        sort_keys=True,
    ) + "\n"


def trajectory_to_csv(trajectory: TrajectoryDTO) -> str:
    """Serialize trajectory rows in deterministic SI/pu column order."""
    if not isinstance(trajectory, TrajectoryDTO):
        raise TypeError("trajectory must be a TrajectoryDTO")
    lengths = {
        len(trajectory.time_s),
        len(trajectory.delta_rad),
        len(trajectory.omega_dev_pu),
    }
    if lengths == {0}:
        raise ValueError("trajectory must contain at least one sample")
    if len(lengths) != 1:
        raise ValueError("trajectory series must have the same length")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("time_s", "delta_rad", "omega_dev_pu"))
    for row in zip(
        trajectory.time_s,
        trajectory.delta_rad,
        trajectory.omega_dev_pu,
        strict=True,
    ):
        writer.writerow(tuple(repr(float(value)) for value in row))
    return stream.getvalue()


def _encode_portable(value: object) -> object:
    if isinstance(value, _PortableDTO):
        return value.to_dict()
    if isinstance(value, (
        learning_content.TheoryTopic, learning_content.LearningBlock,
        learning_content.DisplayQuantity,
        learning_content.TermDefinition, learning_content.CaseGuidance,
        learning_content.LearningStep,
    )):
        return {field.name: _encode_portable(getattr(value, field.name))
                for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_encode_portable(item) for item in value]
    raise TypeError(f"unsupported portable value type: {type(value).__name__}")


def _find_guided_case(case_id: str) -> GuidedCase:
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("guided case_id must be a non-empty string")
    for case in default_guided_cases():
        if case.case_id == case_id:
            return case
    raise ValueError(f"unknown guided case_id: {case_id!r}")


def _guided_summary(case: GuidedCase) -> GuidedCaseSummaryDTO:
    return GuidedCaseSummaryDTO(
        case_id=case.case_id,
        kind=case.kind.value,
        title=case.title,
        difficulty=case.difficulty.value,
        learning_objective=case.learning_objective,
    )


def _question_dto(question: ConceptQuestion) -> ConceptQuestionDTO:
    return ConceptQuestionDTO(
        question_id=question.question_id,
        prompt=question.prompt,
        options=tuple(
            ConceptOptionDTO(option_id=item.option_id, text=item.text)
            for item in question.options
        ),
    )


def _config_dto(config: GuidedSimulationConfig) -> SimulationConfigDTO:
    return SimulationConfigDTO(
        parameters=SMIBParametersDTO(
            H_s=config.parameters.H_s,
            D_pu=config.parameters.D_pu,
            f_base_hz=config.parameters.f_base_hz,
            Pm_pu=config.parameters.Pm_pu,
        ),
        initial_state=SMIBInitialStateDTO(
            delta_rad=config.initial_state.delta_rad,
            omega_dev_pu=config.initial_state.omega_dev_pu,
        ),
        network=SMIBTransientNetworkDTO(
            Pmax_prefault_pu=config.network.Pmax_prefault_pu,
            Pmax_fault_pu=config.network.Pmax_fault_pu,
            Pmax_postfault_pu=config.network.Pmax_postfault_pu,
            t_fault_s=config.network.t_fault_s,
            t_clear_s=config.network.t_clear_s,
        ),
        t_start_s=config.t_start_s,
        t_end_s=config.t_end_s,
        dt_s=config.dt_s,
    )


def _evaluation_dto(evaluation: SMIBClearingTimeEvaluation) -> ClearingTimeEvaluationDTO:
    simulation = evaluation.simulation

    config = GuidedSimulationConfig(
        parameters=simulation.parameters,
        initial_state=simulation.initial_state,
        network=simulation.network,
        t_start_s=simulation.t_start_s,
        t_end_s=simulation.t_end_s,
        dt_s=simulation.dt_s,
    )
    return ClearingTimeEvaluationDTO(
        configuration=_config_dto(config),
        trajectory=TrajectoryDTO(
            time_s=tuple(float(value) for value in simulation.time_s),
            delta_rad=tuple(float(value) for value in simulation.delta_rad),
            omega_dev_pu=tuple(float(value) for value in simulation.omega_dev_pu),
        ),
        first_swing=FirstSwingDTO(
            status=evaluation.first_swing.status.value,
            reason=evaluation.first_swing.reason.value,
            delta_stable_post_rad=evaluation.first_swing.delta_stable_post_rad,
            delta_unstable_post_rad=evaluation.first_swing.delta_unstable_post_rad,
            reversal_bracket=_event_bracket_dto(evaluation.first_swing.reversal_bracket),
            crossing_bracket=_event_bracket_dto(evaluation.first_swing.crossing_bracket),
        ),
        explanation=_explanation_dto(explain_first_swing(evaluation)),
    )


def _config_from_dto(config: SimulationConfigDTO) -> GuidedSimulationConfig:
    parameters = SMIBParameters(
        H_s=config.parameters.H_s,
        D_pu=config.parameters.D_pu,
        f_base_hz=config.parameters.f_base_hz,
        Pm_pu=config.parameters.Pm_pu,
    )
    initial_state = SMIBInitialState(
        delta_rad=config.initial_state.delta_rad,
        omega_dev_pu=config.initial_state.omega_dev_pu,
    )
    network = SMIBTransientNetwork(
        Pmax_prefault_pu=config.network.Pmax_prefault_pu,
        Pmax_fault_pu=config.network.Pmax_fault_pu,
        Pmax_postfault_pu=config.network.Pmax_postfault_pu,
        t_fault_s=config.network.t_fault_s,
        t_clear_s=config.network.t_clear_s,
    )
    return GuidedSimulationConfig(
        parameters=parameters,
        initial_state=initial_state,
        network=network,
        t_start_s=config.t_start_s,
        t_end_s=config.t_end_s,
        dt_s=config.dt_s,
    )


def _event_bracket_dto(bracket: FirstSwingEventBracket | None) -> EventBracketDTO | None:
    if bracket is None:
        return None
    return EventBracketDTO(
        **{field.name: getattr(bracket, field.name) for field in fields(bracket)}
    )


def _explanation_dto(explanation: PedagogicalExplanation) -> ExplanationDTO:
    return ExplanationDTO(
        kind=explanation.kind.value,
        title=explanation.title,
        summary=explanation.summary,
        evidence=tuple(
            ExplanationEvidenceDTO(
                key=item.key,
                value=item.value,
                statement=item.statement,
                unit=item.unit,
            )
            for item in explanation.evidence
        ),
        limitations=explanation.limitations,
        concepts=tuple(item.value for item in explanation.concepts),
    )


def _clearing_bracket_dto(result: SMIBCriticalClearingTimeResult) -> ClearingTimeBracketDTO:
    stable = result.stable_evaluation
    unstable = result.unstable_evaluation
    if stable.simulation.dt_s != unstable.simulation.dt_s:
        raise ValueError("H19 endpoint simulations must retain the same dt_s")
    return ClearingTimeBracketDTO(
        stable_t_clear_s=result.stable_t_clear_s,
        stable_status=stable.first_swing.status.value,
        stable_reason=stable.first_swing.reason.value,
        unstable_t_clear_s=result.unstable_t_clear_s,
        unstable_status=unstable.first_swing.status.value,
        unstable_reason=unstable.first_swing.reason.value,
        bracket_width_s=result.bracket_width_s,
        time_tolerance_s=result.time_tolerance_s,
        time_tolerance_meaning="bisection_stopping_criterion",
        dt_s=stable.simulation.dt_s,
        iterations=result.iterations,
    )


def _solution_dto(case_id: str, solution: PedagogicalSolution) -> PedagogicalSolutionDTO:
    return PedagogicalSolutionDTO(
        case_id=case_id,
        settings=tuple(
            SolutionSettingDTO(key=item.key, value=item.value, unit=item.unit)
            for item in solution.settings
        ),
        explanation=solution.explanation,
        limitation=solution.limitation,
    )


def _attempt_result_dto(record: AttemptRecord) -> GuidedAttemptResultDTO:
    comparison = record.scientific_comparison
    goal = record.goal_evaluation
    score = record.pre_post_score
    local_assessment = (
        LocalAssessmentDTO(False, None, None, None, None)
        if score is None
        else LocalAssessmentDTO(
            assessed=True,
            pre_score=ConceptScoreDTO(score.pre_score.correct, score.pre_score.total),
            post_score=ConceptScoreDTO(score.post_score.correct, score.post_score.total),
            local_delta=score.local_delta,
            limitation=score.limitation,
        )
    )
    return GuidedAttemptResultDTO(
        case_id=record.case_id,
        prediction=record.prediction,
        baseline_config=_config_dto(record.baseline_config),
        attempted_config=_config_dto(record.attempted_config),
        changed_parameters=tuple(
            ParameterChangeDTO(
                key=item.key,
                baseline_value=item.baseline_value,
                attempted_value=item.attempted_value,
                unit=item.unit,
            )
            for item in record.changed_parameters
        ),
        baseline_evaluation=_evaluation_dto(record.baseline_evaluation),
        attempted_evaluation=_evaluation_dto(record.attempted_evaluation),
        scientific_comparison=ScientificComparisonDTO(
            baseline_status=comparison.baseline_status.value,
            attempted_status=comparison.attempted_status.value,
            baseline_reason=comparison.baseline_reason.value,
            attempted_reason=comparison.attempted_reason.value,
            baseline_max_delta_rad=comparison.baseline_max_delta_rad,
            attempted_max_delta_rad=comparison.attempted_max_delta_rad,
            baseline_max_abs_omega_dev_pu=comparison.baseline_max_abs_omega_dev_pu,
            attempted_max_abs_omega_dev_pu=comparison.attempted_max_abs_omega_dev_pu,
        ),
        goal_evaluation=GoalEvaluationDTO(
            achieved=goal.achieved,
            kind=goal.kind.value,
            observed_status=goal.observed_status.value,
            target_status=(goal.target_status.value if goal.target_status else None),
            evidence=goal.evidence,
        ),
        hints_revealed=record.hints_revealed,
        solution_revealed=record.solution_revealed,
        revealed_solution=(
            _solution_dto(record.case_id, record.revealed_solution)
            if record.revealed_solution
            else None
        ),
        pre_answers=_answers_from_domain(record.pre_answers),
        post_answers=_answers_from_domain(record.post_answers),
        local_assessment=local_assessment,
        critical_clearing_bracket=(
            _clearing_bracket_dto(record.critical_clearing_result)
            if record.critical_clearing_result
            else None
        ),
        critical_clearing_explanation=(
            _explanation_dto(record.critical_clearing_explanation)
            if record.critical_clearing_explanation
            else None
        ),
        debrief_summary=record.debrief.summary,
        debrief_limitations=record.debrief.limitations,
    )


def _parse_parameter_values(value: object) -> tuple[ParameterValueDTO, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("changes must be a sequence")
    parsed: list[ParameterValueDTO] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("each change must be a mapping")
        if set(item) not in (
            {"key", "value"},
            {"schema_version", "key", "value"},
        ):
            raise ValueError("each change must contain only key and value")
        _validate_schema_version(item)
        key = item.get("key")
        number = item.get("value")
        if not isinstance(key, str):
            raise TypeError("change key must be a string")
        parsed.append(ParameterValueDTO(key=key, value=_finite_float(key, number)))
    _unique_parameter_mapping(tuple(parsed))
    return tuple(parsed)


def _parse_answers(value: object) -> tuple[QuestionAnswerDTO, ...] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("answers must be a sequence or null")
    answers: list[QuestionAnswerDTO] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("each answer must be a mapping")
        allowed = (
            {"question_id", "option_id"},
            {"schema_version", "question_id", "option_id"},
        )
        if set(item) not in allowed:
            raise ValueError("each answer must contain only question_id and option_id")
        _validate_schema_version(item)
        question_id = item.get("question_id")
        option_id = item.get("option_id")
        if not isinstance(question_id, str) or not isinstance(option_id, str):
            raise TypeError("question_id and option_id must be strings")
        answers.append(QuestionAnswerDTO(question_id, option_id))
    return tuple(answers)


def _validate_schema_version(value: Mapping[str, object]) -> None:
    schema_version = value.get("schema_version", PORTABLE_SCHEMA_VERSION)
    if type(schema_version) is not int or schema_version != PORTABLE_SCHEMA_VERSION:
        raise ValueError("unsupported portable schema_version")


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite JSON number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite JSON number")
    return number


def _unique_parameter_mapping(values: tuple[ParameterValueDTO, ...]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in values:
        if item.key in result:
            raise ValueError(f"duplicate guided parameter change: {item.key!r}")
        result[item.key] = _finite_float(item.key, item.value)
    return result


def _answers_to_domain(
    answers: tuple[QuestionAnswerDTO, ...] | None,
) -> tuple[QuestionAnswer, ...] | None:
    if answers is None:
        return None
    return tuple(QuestionAnswer(item.question_id, item.option_id) for item in answers)


def _answers_from_domain(
    answers: tuple[QuestionAnswer, ...] | None,
) -> tuple[QuestionAnswerDTO, ...] | None:
    if answers is None:
        return None
    return tuple(QuestionAnswerDTO(item.question_id, item.option_id) for item in answers)


# The package snapshot is generated from the public H23 files. Exhaustive
# parity tests make any canonical/projection drift a release-gate failure.
@lru_cache(maxsize=1)
def _h23_projection() -> Mapping[str, Any]:
    projection_path = files("sincrolab.application").joinpath(
        "_h23_reference_projection.json"
    )
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    if type(projection.get("projection_schema_version")) is not int:
        raise RuntimeError("packaged H23 projection has an unsupported schema")
    if projection["projection_schema_version"] != 1:
        raise RuntimeError("packaged H23 projection has an unsupported schema")
    if set(projection) != {
        "projection_schema_version",
        "canonical_source",
        "golden_collection",
        "input_cases",
    }:
        raise RuntimeError("packaged H23 projection has unexpected top-level fields")
    return projection


def _canonical_reference_source() -> str:
    return str(_h23_projection()["canonical_source"])


def _golden_collection() -> Mapping[str, Any]:
    return _as_mapping(_h23_projection()["golden_collection"], "golden_collection")


def _collection_provenance() -> str:
    metadata = _as_mapping(_golden_collection()["metadata"], "metadata")
    return str(metadata["provenance"])


def _reference_definitions() -> tuple[_ReferenceDefinition, ...]:
    cases = _as_mapping(_golden_collection()["cases"], "cases")
    input_cases = _as_mapping(_h23_projection()["input_cases"], "input_cases")
    definitions: list[_ReferenceDefinition] = []
    for case_id, raw_case in cases.items():
        source_case = _as_mapping(raw_case, f"case {case_id}")
        input_case_file = source_case.get("input_case_file")
        input_case = (
            _as_mapping(input_cases[input_case_file], str(input_case_file))
            if isinstance(input_case_file, str)
            else None
        )
        config_source = input_case if input_case is not None else source_case
        definitions.append(
            _ReferenceDefinition(
                case_id=case_id,
                source_case=source_case,
                input_case=input_case,
                config=_reference_config_from_source(config_source),
                runtime_reproduction_scope=_runtime_reproduction_scope(
                    source_case,
                    has_input_case=input_case is not None,
                ),
            )
        )
    return tuple(definitions)


def _runtime_reproduction_scope(
    source_case: Mapping[str, Any],
    *,
    has_input_case: bool,
) -> str:
    if not has_input_case:
        return "query_only"
    expected = _as_mapping(
        source_case["expected_observations"],
        "expected_observations",
    )
    if set(expected) == {"classifications_by_dt_s"}:
        return "selected_time_step_classification"
    return "all_expected_observations"


def _reference_config_from_source(
    source: Mapping[str, Any],
) -> GuidedSimulationConfig:
    parameters_data = _as_mapping(source["smib_parameters"], "smib_parameters")
    network_data = _as_mapping(source["transient_network"], "transient_network")
    initial_data = _as_mapping(source["initial_state"], "initial_state")
    temporal_data = _as_mapping(
        source.get("simulation", source.get("cct_search")),
        "simulation or cct_search",
    )
    if initial_data.get("delta_rad_source") != "prefault_equilibrium":
        raise RuntimeError("unsupported H23 initial-state angle contract")
    parameters = SMIBParameters(**parameters_data)
    network = SMIBTransientNetwork(**network_data)
    return GuidedSimulationConfig(
        parameters=parameters,
        initial_state=SMIBInitialState(
            delta_rad=initial_equilibrium_angle_rad(
                Pm_pu=parameters.Pm_pu,
                Pmax_prefault_pu=network.Pmax_prefault_pu,
            ),
            omega_dev_pu=float(initial_data["omega_dev_pu"]),
        ),
        network=network,
        t_start_s=float(temporal_data["t_start_s"]),
        t_end_s=float(temporal_data["t_end_s"]),
        dt_s=float(temporal_data["dt_s"]),
    )


def _initial_state_contract_dto(
    item: _ReferenceDefinition,
) -> ReferenceInitialStateContractDTO:
    source = item.input_case if item.input_case is not None else item.source_case
    initial = _as_mapping(source["initial_state"], "initial_state")
    return ReferenceInitialStateContractDTO(
        delta_rad_source=str(initial["delta_rad_source"]),
        omega_dev_pu=float(initial["omega_dev_pu"]),
    )


def _expected_observation_dtos(
    source_case: Mapping[str, Any],
) -> tuple[ReferenceExpectedObservationDTO, ...]:
    expected = _as_mapping(
        source_case["expected_observations"],
        "expected_observations",
    )
    observations: list[ReferenceExpectedObservationDTO] = []
    for observation_id, raw_expectation in expected.items():
        if isinstance(raw_expectation, list):
            observations.extend(
                _expected_observation_dto(observation_id, _as_mapping(item, observation_id))
                for item in raw_expectation
            )
        else:
            observations.append(
                _expected_observation_dto(
                    observation_id,
                    _as_mapping(raw_expectation, observation_id),
                )
            )
    return tuple(observations)


def _expected_observation_dto(
    observation_id: str,
    expectation: Mapping[str, Any],
) -> ReferenceExpectedObservationDTO:
    if "value" in expectation:
        expected_field = "value"
    elif "status" in expectation:
        expected_field = "status"
    else:
        upper_bounds = tuple(
            key for key in expectation if key.startswith("upper_bound_")
        )
        if len(upper_bounds) != 1:
            raise RuntimeError(
                f"H23 observation {observation_id!r} lacks one expected value field"
            )
        expected_field = upper_bounds[0]

    tolerance_fields = tuple(
        key for key in expectation if key.startswith("abs_tolerance_")
    )
    if "comparison" in expectation:
        comparison = str(expectation["comparison"])
        comparison_parameter = None
        comparison_value = None
    elif len(tolerance_fields) == 1:
        comparison = "absolute_tolerance"
        comparison_parameter = tolerance_fields[0]
        comparison_value = float(expectation[tolerance_fields[0]])
    else:
        raise RuntimeError(
            f"H23 observation {observation_id!r} lacks comparison semantics"
        )

    expected_value = expectation[expected_field]
    if not isinstance(expected_value, (bool, int, float, str)):
        raise RuntimeError(f"H23 observation {observation_id!r} is not portable")
    dt_s = expectation.get("dt_s")
    return ReferenceExpectedObservationDTO(
        observation_id=observation_id,
        expected_field=expected_field,
        expected_value=expected_value,
        comparison=comparison,
        comparison_parameter=comparison_parameter,
        comparison_value=comparison_value,
        evidence_type=ReferenceEvidenceType(str(expectation["evidence_type"])),
        provenance=str(expectation["provenance"]),
        dt_s=float(dt_s) if dt_s is not None else None,
    )


def _evidence_types_present(
    source_case: Mapping[str, Any],
) -> tuple[ReferenceEvidenceType, ...]:
    present = {
        observation.evidence_type
        for observation in _expected_observation_dtos(source_case)
    }
    metadata = _as_mapping(_golden_collection()["metadata"], "metadata")
    return tuple(
        evidence_type
        for raw_type in metadata["evidence_types"]
        if (evidence_type := ReferenceEvidenceType(str(raw_type))) in present
    )


def _cct_search_dto(
    source_case: Mapping[str, Any],
) -> ReferenceCCTSearchDTO | None:
    raw = source_case.get("cct_search")
    if raw is None:
        return None
    search = _as_mapping(raw, "cct_search")
    return ReferenceCCTSearchDTO(
        stable_t_clear_s=float(search["stable_t_clear_s"]),
        unstable_t_clear_s=float(search["unstable_t_clear_s"]),
        t_start_s=float(search["t_start_s"]),
        t_end_s=float(search["t_end_s"]),
        dt_s=float(search["dt_s"]),
        time_tolerance_s=float(search["time_tolerance_s"]),
        angle_tolerance_rad=float(search["angle_tolerance_rad"]),
        max_iterations=int(search["max_iterations"]),
        tolerance_interpretation=str(search["tolerance_interpretation"]),
    )


def _external_reference_dto(
    source_case: Mapping[str, Any],
) -> ReferenceExternalNumericalDTO | None:
    raw = source_case.get("external_reference")
    if raw is None:
        return None
    reference = _as_mapping(raw, "external_reference")
    return ReferenceExternalNumericalDTO(
        solver=str(reference["solver"]),
        method=str(reference["method"]),
        rtol=float(reference["rtol"]),
        atol=float(reference["atol"]),
        usage=str(reference["usage"]),
    )


def _verify_transient_reference_observations(
    expected: tuple[ReferenceExpectedObservationDTO, ...],
    evaluation: SMIBClearingTimeEvaluation,
) -> tuple[ReferenceObservationResultDTO, ...]:
    simulation = evaluation.simulation
    network = simulation.network
    fault_index = _event_index(simulation.time_s, network.t_fault_s)
    clearing_index = _event_index(simulation.time_s, network.t_clear_s)
    fault_rhs = smib_swing_rhs(
        network.t_fault_s,
        np.array(
            [
                simulation.delta_rad[fault_index],
                simulation.omega_dev_pu[fault_index],
            ],
            dtype=np.float64,
        ),
        simulation.parameters,
        Pmax_pu=network.Pmax_fault_pu,
    )
    observed: dict[str, bool | float | int | str] = {
        "fault_event_occurrences": sum(
            float(value) == network.t_fault_s for value in simulation.time_s
        ),
        "clearing_event_occurrences": sum(
            float(value) == network.t_clear_s for value in simulation.time_s
        ),
        "fault_initial_acceleration_pu_per_s": float(fault_rhs[1]),
        "delta_rad_at_clearing": float(simulation.delta_rad[clearing_index]),
        "omega_dev_pu_at_clearing": float(
            simulation.omega_dev_pu[clearing_index]
        ),
        "first_swing_status": evaluation.first_swing.status.name,
        "first_swing_reason": evaluation.first_swing.reason.name,
    }
    if any(
        item.observation_id == "crossing_bracket_speed_sign" for item in expected
    ):
        bracket = evaluation.first_swing.crossing_bracket
        observed["crossing_bracket_speed_sign"] = (
            "POSITIVE_AT_BOTH_SAMPLES"
            if bracket is not None
            and bracket.left_omega_dev_pu > 0.0
            and bracket.right_omega_dev_pu > 0.0
            else "NOT_POSITIVE_AT_BOTH_SAMPLES"
        )
    expected_ids = {item.observation_id for item in expected}
    if expected_ids != set(observed):
        raise RuntimeError(
            "runtime H23 verifier and canonical transient observations diverged"
        )
    return tuple(
        _observation_result(item, observed[item.observation_id])
        for item in expected
    )


def _verify_selected_classification(
    expected: tuple[ReferenceExpectedObservationDTO, ...],
    evaluation: SMIBClearingTimeEvaluation,
    *,
    dt_s: float,
) -> tuple[ReferenceObservationResultDTO, ...]:
    selected = tuple(item for item in expected if item.dt_s == dt_s)
    if len(selected) != 1:
        raise RuntimeError("H23 adversarial projection lacks one selected claim")
    return (
        _observation_result(selected[0], evaluation.first_swing.status.name),
    )


def _observation_result(
    expected: ReferenceExpectedObservationDTO,
    observed_value: bool | float | int | str,
) -> ReferenceObservationResultDTO:
    if expected.comparison == "exact":
        matches = observed_value == expected.expected_value
    elif expected.comparison == "absolute_tolerance":
        if expected.comparison_value is None:
            raise RuntimeError("absolute-tolerance H23 claim lacks its tolerance")
        matches = abs(
            _numeric_observation(observed_value)
            - _numeric_observation(expected.expected_value)
        ) <= expected.comparison_value
    elif expected.comparison == "less_than":
        matches = _numeric_observation(observed_value) < _numeric_observation(
            expected.expected_value
        )
    else:
        raise RuntimeError(
            f"unsupported H23 comparison semantics: {expected.comparison!r}"
        )
    return ReferenceObservationResultDTO(
        expected=expected,
        observed_value=observed_value,
        matches_expected=matches,
    )


def _numeric_observation(value: bool | float | int | str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError("H23 numerical comparison received a non-number")
    return float(value)


def _event_index(values: Sequence[float], event_time_s: float) -> int:
    indices = tuple(
        index for index, value in enumerate(values) if float(value) == event_time_s
    )
    if len(indices) != 1:
        raise RuntimeError("H23 event observation requires exactly one event sample")
    return indices[0]


def _as_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"packaged H23 {name} must be a mapping")
    return value


def _find_reference_case(case_id: str) -> _ReferenceDefinition:
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("reference case_id must be a non-empty string")
    for item in _reference_definitions():
        if item.case_id == case_id:
            return item
    raise ValueError(f"unknown reference case_id: {case_id!r}")


__all__ = [
    "ClearingTimeBracketDTO",
    "ClearingTimeEvaluationDTO",
    "ConceptOptionDTO",
    "ConceptQuestionDTO",
    "ConceptScoreDTO",
    "EditableParameterDTO",
    "EventBracketDTO",
    "ExplanationDTO",
    "ExplanationEvidenceDTO",
    "FirstSwingDTO",
    "GoalEvaluationDTO",
    "GuidedAttemptRequest",
    "GuidedAttemptResultDTO",
    "GuidedCaseDTO",
    "GuidedCaseSummaryDTO",
    "GuidedHintsDTO",
    "LocalAssessmentDTO",
    "PORTABLE_API_VERSION",
    "PORTABLE_SCHEMA_VERSION",
    "ParameterChangeDTO",
    "ParameterValueDTO",
    "PedagogicalSolutionDTO",
    "PortableCapabilities",
    "QuestionAnswerDTO",
    "RELEASE_TARGET",
    "ReferenceCaseDTO",
    "ReferenceCaseResultDTO",
    "ReferenceCaseSummaryDTO",
    "ReferenceEvidenceType",
    "ReferenceCCTSearchDTO",
    "ReferenceExpectedObservationDTO",
    "ReferenceExternalNumericalDTO",
    "ReferenceInitialStateContractDTO",
    "ReferenceObservationResultDTO",
    "SMIBInitialStateDTO",
    "SMIBParametersDTO",
    "SMIBTransientNetworkDTO",
    "ScientificComparisonDTO",
    "evaluate_transient",
    "SimulationConfigDTO",
    "SolutionSettingDTO",
    "TrajectoryDTO",
    "dumps_portable",
    "get_capabilities",
    "get_guided_case",
    "get_guided_hints",
    "get_guided_solution",
    "get_reference_case",
    "list_guided_cases",
    "list_reference_cases",
    "reproduce_reference_case",
    "run_guided_attempt",
    "trajectory_to_csv",
]
