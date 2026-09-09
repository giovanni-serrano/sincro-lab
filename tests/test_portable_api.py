import json
from dataclasses import replace
from pathlib import Path

import pytest

import sincrolab.application as application_module
import sincrolab.application.portable as portable_module
from sincrolab.application import (
    GuidedAttemptRequest,
    ParameterValueDTO,
    QuestionAnswerDTO,
    ReferenceEvidenceType,
    dumps_portable,
    evaluate_transient,
    get_capabilities,
    get_guided_case,
    get_guided_hints,
    get_guided_solution,
    get_reference_case,
    list_guided_cases,
    list_reference_cases,
    reproduce_reference_case,
    run_portable_guided_attempt,
    trajectory_to_csv,
)
from sincrolab.models import initial_equilibrium_angle_rad
from sincrolab.application.guided_learning import (
    default_guided_cases,
    prepare_guided_attempt,
    run_guided_attempt,
)


REFERENCE_CASES = Path(__file__).parents[1] / "reference_cases"
GOLDEN_CASE_PATH = REFERENCE_CASES / "smib_v0_1_golden_cases.json"
PROJECTION_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "sincrolab"
    / "application"
    / "_h23_reference_projection.json"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _portable_observations_as_source(case: object) -> dict[str, object]:
    reconstructed: dict[str, object] = {}
    for observation in case.expected_observations:
        claim: dict[str, object] = {}
        if observation.dt_s is not None:
            claim["dt_s"] = observation.dt_s
        claim[observation.expected_field] = observation.expected_value
        if observation.comparison == "absolute_tolerance":
            claim[observation.comparison_parameter] = observation.comparison_value
        else:
            claim["comparison"] = observation.comparison
        claim["evidence_type"] = observation.evidence_type.value
        claim["provenance"] = observation.provenance
        if observation.dt_s is None:
            reconstructed[observation.observation_id] = claim
        else:
            reconstructed.setdefault(observation.observation_id, []).append(claim)
    return reconstructed


def _without_schema(value: object) -> dict[str, object]:
    result = value.to_dict()
    result.pop("schema_version")
    return result


def _inertia_request(**changes: object) -> GuidedAttemptRequest:
    values = tuple(
        ParameterValueDTO(key=key, value=float(value))
        for key, value in changes.items()
    )
    return GuidedAttemptRequest(
        case_id="controlled-inertia-effect",
        prediction="smaller excursion",
        changes=values,
    )


def _all_key_names(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_all_key_names(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_key_names(child) for child in value))
    return set()


def test_portable_module_exports_only_deliberate_contracts() -> None:
    exported = portable_module.__all__
    assert len(exported) == len(set(exported))
    assert all(not name.startswith("_") for name in exported)
    assert all(hasattr(portable_module, name) for name in exported)
    assert {
        "GuidedAttemptRequest",
        "GuidedAttemptResultDTO",
        "SimulationConfigDTO",
        "ReferenceCaseResultDTO",
        "evaluate_transient",
        "run_guided_attempt",
        "reproduce_reference_case",
        "dumps_portable",
        "trajectory_to_csv",
    } <= set(exported)
    assert {"SMIBParameters", "GuidedCase", "json", "csv", "Any"}.isdisjoint(
        exported
    )


def test_reference_contracts_are_reexported_by_application_package() -> None:
    names = {
        "ReferenceCCTSearchDTO",
        "ReferenceCaseDTO",
        "ReferenceCaseResultDTO",
        "ReferenceCaseSummaryDTO",
        "ReferenceEvidenceType",
        "ReferenceExpectedObservationDTO",
        "ReferenceExternalNumericalDTO",
        "ReferenceInitialStateContractDTO",
        "ReferenceObservationResultDTO",
    }
    assert names <= set(application_module.__all__)
    assert all(
        getattr(application_module, name) is getattr(portable_module, name)
        for name in names
    )


def test_capabilities_describe_shared_portable_surface() -> None:
    capabilities = get_capabilities()
    assert capabilities.portable_api_version == "1.0"
    assert capabilities.release_target == "v0.1.0-core"
    assert capabilities.scientific_operations == ("evaluate_transient",)
    assert capabilities.trajectory_fields == (
        "time_s",
        "delta_rad",
        "omega_dev_pu",
    )
    assert capabilities.export_formats == ("json", "csv")


def test_guided_catalog_is_ordered_and_does_not_reveal_answers() -> None:
    summaries = list_guided_cases()
    assert tuple(item.case_id for item in summaries) == (
        "late-clearing-bracket",
        "controlled-inertia-effect",
        "first-swing-event-evidence",
    )
    serialized = dumps_portable(summaries)
    assert "correct_option_id" not in serialized
    assert "pedagogical_solution" not in serialized
    assert "hints" not in serialized


def test_guided_case_exposes_typed_bounds_without_answer_key() -> None:
    case = get_guided_case("controlled-inertia-effect")
    assert case.editable_parameters[0].key == "H_s"
    assert case.editable_parameters[0].unit == "s"
    assert case.baseline_config.parameters.H_s == 3.5
    assert case.conceptual_questions[0].options[0].option_id == "a"
    assert "correct_option_id" not in dumps_portable(case)


def test_guided_hints_are_progressive_and_solution_is_explicit() -> None:
    first = get_guided_hints("late-clearing-bracket", 1)
    second = get_guided_hints("late-clearing-bracket", 2)
    assert second.hints[:1] == first.hints
    assert len(first.hints) == 1
    solution = get_guided_solution("late-clearing-bracket")
    assert solution.settings[0].key == "t_clear_s"
    assert "una" in solution.explanation.lower()
    assert "no un ajuste de protección" in solution.limitation


def test_guided_request_round_trips_through_json_mapping() -> None:
    request = GuidedAttemptRequest(
        case_id="controlled-inertia-effect",
        prediction="smaller excursion",
        changes=(ParameterValueDTO("H_s", 6.0),),
        hints_revealed=1,
        pre_answers=(
            QuestionAnswerDTO("accelerating_power", "a"),
            QuestionAnswerDTO("first_swing_evidence", "b"),
        ),
        post_answers=(
            QuestionAnswerDTO("accelerating_power", "a"),
            QuestionAnswerDTO("first_swing_evidence", "b"),
        ),
    )
    decoded = json.loads(dumps_portable(request))
    assert GuidedAttemptRequest.from_dict(decoded) == request


def test_guided_request_requires_top_level_schema_version() -> None:
    decoded = json.loads(dumps_portable(_inertia_request(H_s=6.0)))
    del decoded["schema_version"]
    with pytest.raises(ValueError, match="requires schema_version"):
        GuidedAttemptRequest.from_dict(decoded)


@pytest.mark.parametrize("schema_version", [True, 1.0, "1", 2])
def test_guided_request_requires_integer_schema_version(
    schema_version: object,
) -> None:
    decoded = json.loads(dumps_portable(_inertia_request(H_s=6.0)))
    decoded["schema_version"] = schema_version
    with pytest.raises(ValueError, match="schema_version"):
        GuidedAttemptRequest.from_dict(decoded)


def test_guided_request_rejects_inconsistent_nested_schema_version() -> None:
    decoded = json.loads(dumps_portable(_inertia_request(H_s=6.0)))
    decoded["changes"][0]["schema_version"] = 2
    with pytest.raises(ValueError, match="schema_version"):
        GuidedAttemptRequest.from_dict(decoded)


@pytest.mark.parametrize("value", ["6.0", True, float("nan"), float("inf")])
def test_guided_request_requires_finite_json_numbers(value: object) -> None:
    decoded = json.loads(dumps_portable(_inertia_request(H_s=6.0)))
    decoded["changes"][0]["value"] = value
    with pytest.raises((TypeError, ValueError), match="finite JSON number"):
        GuidedAttemptRequest.from_dict(decoded)


@pytest.mark.parametrize(
    ("attempt_request", "message"),
    [
        (
            GuidedAttemptRequest(
                "controlled-inertia-effect",
                "not-an-option",
            ),
            "prediction",
        ),
        (
            _inertia_request(t_clear_s=0.2),
            "not editable",
        ),
        (
            _inertia_request(H_s=100.0),
            "editable bounds",
        ),
    ],
)
def test_guided_user_errors_remain_explicit(
    attempt_request: GuidedAttemptRequest,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        run_portable_guided_attempt(attempt_request)


def test_guided_attempt_matches_direct_h25_evidence() -> None:
    request = _inertia_request(H_s=6.0)
    portable = run_portable_guided_attempt(request)
    case = next(
        case
        for case in default_guided_cases()
        if case.case_id == request.case_id
    )
    direct = run_guided_attempt(
        prepare_guided_attempt(case, request.prediction),
        {"H_s": 6.0},
    )
    assert portable.attempted_evaluation.first_swing.status == (
        direct.attempted_evaluation.first_swing.status.value
    )
    assert portable.attempted_evaluation.first_swing.reason == (
        direct.attempted_evaluation.first_swing.reason.value
    )
    assert portable.scientific_comparison.attempted_max_delta_rad == (
        direct.scientific_comparison.attempted_max_delta_rad
    )


def test_not_assessed_is_distinct_from_zero_score() -> None:
    result = run_portable_guided_attempt(_inertia_request(H_s=6.0))
    assert result.local_assessment.assessed is False
    assert result.local_assessment.pre_score is None
    assert result.local_assessment.post_score is None
    assert result.local_assessment.local_delta is None


def test_complete_pre_post_assessment_is_preserved() -> None:
    answers = (
        QuestionAnswerDTO("accelerating_power", "a"),
        QuestionAnswerDTO("first_swing_evidence", "b"),
    )
    request = replace(
        _inertia_request(H_s=6.0),
        pre_answers=answers,
        post_answers=answers,
    )
    result = run_portable_guided_attempt(request)
    assert result.local_assessment.assessed is True
    assert result.local_assessment.pre_score.correct == 2
    assert result.local_assessment.pre_score.total == 2
    assert result.local_assessment.local_delta == 0


def test_incomplete_pre_post_pair_fails_instead_of_scoring_omissions() -> None:
    request = replace(
        _inertia_request(H_s=6.0),
        pre_answers=(QuestionAnswerDTO("accelerating_power", "a"),),
    )
    with pytest.raises(ValueError, match="supplied together"):
        run_portable_guided_attempt(request)


def test_json_is_deterministic_and_arrays_are_explicit_lists() -> None:
    result = run_portable_guided_attempt(_inertia_request(H_s=6.0))
    first = dumps_portable(result)
    second = dumps_portable(result)
    decoded = json.loads(first)
    trajectory = decoded["attempted_evaluation"]["trajectory"]
    assert first == second
    assert isinstance(trajectory["time_s"], list)
    assert isinstance(trajectory["delta_rad"], list)
    assert isinstance(trajectory["omega_dev_pu"], list)
    assert trajectory["time_s"] == sorted(trajectory["time_s"])


def test_json_contains_no_local_or_personal_metadata() -> None:
    serialized = dumps_portable(
        run_portable_guided_attempt(_inertia_request(H_s=6.0))
    )
    lowered = serialized.lower()
    for forbidden in (
        "c:\\\\users",
        "/home/",
        "hostname",
        "timestamp",
        "uuid",
        "telemetry",
        "analytics",
        "working_directory",
    ):
        assert forbidden not in lowered


def test_csv_has_explicit_header_and_exact_portable_order() -> None:
    result = reproduce_reference_case("stable_transient")
    trajectory = result.evaluation.trajectory
    csv_text = trajectory_to_csv(trajectory)
    lines = csv_text.splitlines()
    assert lines[0] == "time_s,delta_rad,omega_dev_pu"
    assert lines[1] == ",".join(
        repr(float(value))
        for value in (
            trajectory.time_s[0],
            trajectory.delta_rad[0],
            trajectory.omega_dev_pu[0],
        )
    )
    assert len(lines) == len(trajectory.time_s) + 1


def test_portable_module_contains_no_parallel_h23_case_catalog() -> None:
    source = (
        Path(portable_module.__file__).read_text(encoding="utf-8")
    )
    canonical = _load_json(GOLDEN_CASE_PATH)
    assert all(case_id not in source for case_id in canonical["cases"])


def test_packaged_h23_projection_has_exhaustive_canonical_parity() -> None:
    canonical = _load_json(GOLDEN_CASE_PATH)
    projection = _load_json(PROJECTION_PATH)
    assert projection["projection_schema_version"] == 1
    assert projection["canonical_source"] == (
        "reference_cases/smib_v0_1_golden_cases.json"
    )
    assert projection["golden_collection"] == canonical

    cases = canonical["cases"]
    expected_input_files = {
        case["input_case_file"]
        for case in cases.values()
        if "input_case_file" in case
    }
    assert set(projection["input_cases"]) == expected_input_files
    for input_file in expected_input_files:
        assert projection["input_cases"][input_file] == _load_json(
            REFERENCE_CASES / input_file
        )


def test_reference_catalog_preserves_h23_case_ids_and_evidence_sets() -> None:
    canonical = _load_json(GOLDEN_CASE_PATH)
    summaries = list_reference_cases()
    assert tuple(item.case_id for item in summaries) == tuple(canonical["cases"])
    all_present = {
        evidence_type
        for item in summaries
        for evidence_type in item.evidence_types_present
    }
    assert all_present == set(ReferenceEvidenceType)
    assert all("ORACLE" not in item.case_id for item in summaries)

    for summary in summaries:
        source = canonical["cases"][summary.case_id]
        claim_types = {
            expectation["evidence_type"]
            for raw in source["expected_observations"].values()
            for expectation in (raw if isinstance(raw, list) else [raw])
        }
        assert {item.value for item in summary.evidence_types_present} == claim_types
        assert summary.purpose == source["purpose"]
        assert summary.limitation == source["limitations"]


@pytest.mark.parametrize(
    "case_id",
    [
        "stable_transient",
        "unstable_transient",
        "adversarial_time_step",
        "classic_undamped",
        "scipy_cross_checked_transient",
    ],
)
def test_reference_case_projection_preserves_every_h23_field(case_id: str) -> None:
    canonical = _load_json(GOLDEN_CASE_PATH)
    source_case = canonical["cases"][case_id]
    portable = get_reference_case(case_id)
    input_file = source_case.get("input_case_file")
    config_source = (
        _load_json(REFERENCE_CASES / input_file) if input_file else source_case
    )
    temporal_source = config_source.get(
        "simulation",
        config_source.get("cct_search"),
    )

    assert portable.case_id == case_id
    assert portable.purpose == source_case["purpose"]
    assert portable.limitation == source_case["limitations"]
    assert portable.input_case_file == input_file
    assert portable.canonical_source == (
        "reference_cases/smib_v0_1_golden_cases.json"
    )
    assert portable.projection_source == (
        "sincrolab.application/_h23_reference_projection.json"
    )
    assert portable.collection_provenance == canonical["metadata"]["provenance"]
    assert portable.initial_state_contract.delta_rad_source == (
        config_source["initial_state"]["delta_rad_source"]
    )
    assert portable.initial_state_contract.omega_dev_pu == (
        config_source["initial_state"]["omega_dev_pu"]
    )
    assert _without_schema(portable.configuration.parameters) == (
        config_source["smib_parameters"]
    )
    assert _without_schema(portable.configuration.network) == (
        config_source["transient_network"]
    )
    assert portable.configuration.initial_state.omega_dev_pu == (
        config_source["initial_state"]["omega_dev_pu"]
    )
    assert portable.configuration.initial_state.delta_rad == (
        initial_equilibrium_angle_rad(
            Pm_pu=config_source["smib_parameters"]["Pm_pu"],
            Pmax_prefault_pu=config_source["transient_network"][
                "Pmax_prefault_pu"
            ],
        )
    )
    assert portable.configuration.t_start_s == temporal_source["t_start_s"]
    assert portable.configuration.t_end_s == temporal_source["t_end_s"]
    assert portable.configuration.dt_s == temporal_source["dt_s"]
    assert _portable_observations_as_source(portable) == (
        source_case["expected_observations"]
    )

    if "cct_search" in source_case:
        assert _without_schema(portable.cct_search) == source_case["cct_search"]
    else:
        assert portable.cct_search is None
    if "external_reference" in source_case:
        assert _without_schema(portable.external_reference) == (
            source_case["external_reference"]
        )
    else:
        assert portable.external_reference is None

    expected_scope = (
        "query_only"
        if input_file is None
        else "selected_time_step_classification"
        if set(source_case["expected_observations"]) == {"classifications_by_dt_s"}
        else "all_expected_observations"
    )
    assert portable.runtime_reproduction_scope == expected_scope


@pytest.mark.parametrize(
    "case_id",
    ["stable_transient", "unstable_transient"],
)
def test_reference_run_verifies_all_canonical_transient_observations(
    case_id: str,
) -> None:
    canonical_case = _load_json(GOLDEN_CASE_PATH)["cases"][case_id]
    result = reproduce_reference_case(case_id)
    assert result.verification_scope == "all_expected_observations"
    assert result.all_reported_observations_match_expected is True
    assert tuple(item.expected.observation_id for item in result.observations) == tuple(
        canonical_case["expected_observations"]
    )
    assert all(item.matches_expected for item in result.observations)
    assert {
        item.expected.observation_id: (
            item.expected.evidence_type.value,
            item.expected.provenance,
        )
        for item in result.observations
    } == {
        observation_id: (
            expectation["evidence_type"],
            expectation["provenance"],
        )
        for observation_id, expectation in canonical_case[
            "expected_observations"
        ].items()
    }
    payload = json.loads(dumps_portable(result))
    assert "matches_expected" not in {
        key for key in payload if key != "observations"
    }
    assert payload["all_reported_observations_match_expected"] is True


@pytest.mark.parametrize("dt_s", [0.2, 0.1, 0.05, 0.025])
def test_adversarial_reference_verifies_selected_canonical_claim(dt_s: float) -> None:
    canonical_case = _load_json(GOLDEN_CASE_PATH)["cases"][
        "adversarial_time_step"
    ]
    expected = next(
        item
        for item in canonical_case["expected_observations"][
            "classifications_by_dt_s"
        ]
        if item["dt_s"] == dt_s
    )
    result = reproduce_reference_case("adversarial_time_step", dt_s=dt_s)
    assert result.verification_scope == "selected_time_step_classification"
    assert result.all_reported_observations_match_expected is True
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.expected.observation_id == "classifications_by_dt_s"
    assert observation.expected.expected_value == expected["status"]
    assert observation.observed_value == expected["status"]
    assert observation.expected.evidence_type.value == expected["evidence_type"]
    assert observation.expected.provenance == expected["provenance"]
    assert result.limitation == canonical_case["limitations"]


def test_adversarial_reference_requires_an_explicit_retained_resolution() -> None:
    with pytest.raises(ValueError, match="dt_s is required"):
        reproduce_reference_case("adversarial_time_step")


def test_query_only_references_preserve_granular_claims_without_runtime_solver() -> None:
    canonical = _load_json(GOLDEN_CASE_PATH)
    for case_id in ("classic_undamped", "scipy_cross_checked_transient"):
        case = get_reference_case(case_id)
        source = canonical["cases"][case_id]
        assert case.runtime_reproduction_scope == "query_only"
        assert _portable_observations_as_source(case) == (
            source["expected_observations"]
        )
        with pytest.raises(ValueError, match="query-only"):
            reproduce_reference_case(case_id)

    scipy_case = get_reference_case("scipy_cross_checked_transient")
    assert scipy_case.external_reference.usage == "test_only"
    assert scipy_case.evidence_types_present == (
        ReferenceEvidenceType.EXTERNAL_NUMERICAL_ORACLE,
    )


def test_h19_portable_result_is_a_bracket_without_exact_cct_fields() -> None:
    result = run_portable_guided_attempt(
        GuidedAttemptRequest(
            case_id="late-clearing-bracket",
            prediction="stable",
            changes=(ParameterValueDTO("t_clear_s", 0.2),),
        )
    )
    bracket = result.critical_clearing_bracket
    assert bracket.stable_t_clear_s < bracket.unstable_t_clear_s
    assert bracket.stable_status == "stable"
    assert bracket.unstable_status == "unstable"
    assert bracket.bracket_width_s <= bracket.time_tolerance_s
    assert bracket.time_tolerance_meaning == "bisection_stopping_criterion"
    keys = _all_key_names(json.loads(dumps_portable(result)))
    assert "cct_estimate_s" not in keys
    assert "exact_cct_s" not in keys
    assert "true_cct_s" not in keys
    assert "uncertainty_s" not in keys


def test_indeterminate_status_and_reason_are_serialized_without_reclassification() -> None:
    config = get_guided_case("late-clearing-bracket").baseline_config
    short = replace(
        config,
        network=replace(config.network, t_clear_s=0.2),
        t_end_s=0.3,
    )
    result = evaluate_transient(short)
    assert result.first_swing.status == "indeterminate"
    assert result.first_swing.reason == "horizon_ended_before_event"
    decoded = json.loads(dumps_portable(result))
    assert decoded["first_swing"]["status"] == "indeterminate"
    assert decoded["first_swing"]["reason"] == "horizon_ended_before_event"


def test_h24_explanation_is_transported_without_semantic_change() -> None:
    result = reproduce_reference_case("stable_transient")
    explanation = result.evaluation.explanation
    evidence = {item.key: item.value for item in explanation.evidence}
    assert explanation.kind == "first_swing"
    assert evidence["status"] == "stable"
    assert evidence["reason"] == "reversal_before_crossing"
    assert "muestreada" in explanation.summary.lower()
