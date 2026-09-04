from dataclasses import fields, replace

import numpy as np
import pytest

from sincrolab.analysis import FirstSwingReason, FirstSwingStatus
from sincrolab.application import (
    AttemptRecord,
    PreparedGuidedAttempt,
    QuestionAnswer,
    default_guided_cases,
    prepare_guided_attempt,
    reveal_progressive_hints,
    run_guided_attempt,
    score_concept_answers,
)


def _case(case_id: str):
    return next(case for case in default_guided_cases() if case.case_id == case_id)


def _prepare(case_id: str, prediction: str | None = None):
    guided_case = _case(case_id)
    return prepare_guided_attempt(
        guided_case,
        prediction or guided_case.prediction_options[0],
    )


def test_catalog_has_three_unique_deterministic_cases() -> None:
    first = default_guided_cases()
    second = default_guided_cases()

    assert len(first) == 3
    assert first == second
    assert len({case.case_id for case in first}) == 3
    assert all(case.baseline_config == copy.baseline_config for case, copy in zip(first, second))
    for case in first:
        editable = case.editable_parameters[0]
        expected = (
            case.baseline_config.parameters.H_s
            if editable.key == "H_s"
            else case.baseline_config.network.t_clear_s
        )
        assert editable.baseline_value == expected


def test_prediction_is_required_before_execution() -> None:
    case = _case("late-clearing-bracket")

    with pytest.raises(ValueError, match="prediction"):
        prepare_guided_attempt(case, "not-a-valid-prediction")
    with pytest.raises(ValueError, match="prediction"):
        PreparedGuidedAttempt(case, "not-a-valid-prediction")
    with pytest.raises(TypeError, match="prepared guided attempt"):
        run_guided_attempt(case, {})  # type: ignore[arg-type]
    assert "guided_case" not in {field.name for field in fields(AttemptRecord)}


def test_direct_valid_preparation_can_execute() -> None:
    case = _case("first-swing-event-evidence")
    prepared = PreparedGuidedAttempt(case, "stable")

    record = run_guided_attempt(prepared, {})

    assert record.prediction == "stable"


@pytest.mark.parametrize(
    ("case_id", "wrong_baseline"),
    (
        ("controlled-inertia-effect", 4.0),
        ("late-clearing-bracket", 0.3),
    ),
)
def test_editable_metadata_must_match_scientific_baseline(
    case_id: str,
    wrong_baseline: float,
) -> None:
    case = _case(case_id)
    editable = replace(
        case.editable_parameters[0],
        baseline_value=wrong_baseline,
    )

    with pytest.raises(ValueError, match="baseline configuration"):
        replace(case, editable_parameters=(editable,))


def test_editable_bounds_and_unknown_parameter_are_rejected() -> None:
    prepared = _prepare("controlled-inertia-effect")

    with pytest.raises(ValueError, match="bounds"):
        run_guided_attempt(prepared, {"H_s": 9.0})
    with pytest.raises(ValueError, match="not editable"):
        run_guided_attempt(prepared, {"Pm_pu": 0.8})


def test_changed_parameter_record_is_structured_and_ordered() -> None:
    record = run_guided_attempt(
        _prepare("controlled-inertia-effect"),
        {"H_s": 6.0},
    )

    assert [(change.key, change.baseline_value, change.attempted_value, change.unit)
            for change in record.changed_parameters] == [("H_s", 3.5, 6.0, "s")]
    assert record.baseline_config.parameters.Pm_pu == record.attempted_config.parameters.Pm_pu
    assert record.baseline_config.network == record.attempted_config.network
    assert record.baseline_config.initial_state == record.attempted_config.initial_state
    assert record.baseline_config.t_end_s == record.attempted_config.t_end_s
    assert record.baseline_config.dt_s == record.attempted_config.dt_s


def test_hints_are_progressive_and_solution_is_optional() -> None:
    case = _case("first-swing-event-evidence")

    assert reveal_progressive_hints(case, 1) == (case.hints[0],)
    assert reveal_progressive_hints(case, 2) == case.hints
    hidden = run_guided_attempt(prepare_guided_attempt(case, "stable"), {})
    revealed = run_guided_attempt(
        prepare_guided_attempt(case, "stable"),
        {},
        reveal_solution=True,
    )
    assert hidden.revealed_solution is None
    assert not hidden.solution_revealed
    assert revealed.revealed_solution == case.pedagogical_solution
    assert "One pedagogical solution" in revealed.revealed_solution.explanation
    assert "not" in revealed.revealed_solution.limitation


def test_attempt_retains_prediction_baseline_attempt_and_h24_explanations() -> None:
    record = run_guided_attempt(
        _prepare("first-swing-event-evidence", "unstable"),
        {"t_clear_s": 0.35},
    )

    assert record.prediction == "unstable"
    assert record.baseline_config.network.t_clear_s == 0.2
    assert record.attempted_config.network.t_clear_s == 0.35
    assert record.baseline_explanation == record.debrief.baseline_explanation
    assert record.attempted_explanation == record.debrief.attempted_explanation


def test_late_clearing_uses_real_h15_and_h19_results() -> None:
    record = run_guided_attempt(
        _prepare("late-clearing-bracket", "stable"),
        {"t_clear_s": 0.2},
    )

    assert record.baseline_evaluation.first_swing.status is FirstSwingStatus.UNSTABLE
    assert record.attempted_evaluation.first_swing.status is FirstSwingStatus.STABLE
    assert record.goal_evaluation.achieved
    result = record.critical_clearing_result
    assert result is not None
    assert result.stable_t_clear_s < result.unstable_t_clear_s
    explanation = record.critical_clearing_explanation
    assert explanation is not None
    assert {evidence.key for evidence in explanation.evidence} >= {
        "stable_t_clear_s",
        "unstable_t_clear_s",
        "time_tolerance_s",
    }
    combined = " ".join((explanation.summary, *explanation.limitations)).lower()
    assert "exact cct" not in combined
    assert "stopping criterion" in combined
    assert "uncertainty" in combined


def test_inertia_case_changes_only_h_and_reports_observed_metrics() -> None:
    record = run_guided_attempt(
        _prepare("controlled-inertia-effect", "smaller excursion"),
        {"H_s": 6.0},
    )

    assert tuple(change.key for change in record.changed_parameters) == ("H_s",)
    assert record.baseline_config.network == record.attempted_config.network
    assert record.scientific_comparison.baseline_max_delta_rad != (
        record.scientific_comparison.attempted_max_delta_rad
    )
    text = " ".join((record.debrief.summary, *record.debrief.limitations)).lower()
    assert "only h_s changed" in text
    assert "higher inertia always" in text
    assert "does not imply" in text


def test_first_swing_case_preserves_real_stable_and_unstable_reasons() -> None:
    stable = run_guided_attempt(
        _prepare("first-swing-event-evidence", "stable"),
        {},
    )
    unstable = run_guided_attempt(
        _prepare("first-swing-event-evidence", "unstable"),
        {"t_clear_s": 0.35},
    )

    assert stable.attempted_evaluation.first_swing.status is FirstSwingStatus.STABLE
    assert stable.attempted_evaluation.first_swing.reason is (
        FirstSwingReason.REVERSAL_BEFORE_CROSSING
    )
    assert unstable.attempted_evaluation.first_swing.status is FirstSwingStatus.UNSTABLE
    assert unstable.attempted_evaluation.first_swing.reason is (
        FirstSwingReason.CROSSING_BEFORE_REVERSAL
    )
    assert unstable.attempted_evaluation.first_swing.crossing_bracket is not None
    assert unstable.attempted_explanation.evidence[0].value == "unstable"


def test_indeterminate_is_preserved_instead_of_forced_to_target() -> None:
    case = _case("first-swing-event-evidence")
    short_case = replace(
        case,
        baseline_config=replace(case.baseline_config, t_end_s=0.201),
    )
    record = run_guided_attempt(
        prepare_guided_attempt(short_case, "indeterminate"),
        {},
    )

    assert record.attempted_evaluation.first_swing.status is (
        FirstSwingStatus.INDETERMINATE
    )
    assert record.attempted_evaluation.first_swing.reason is (
        FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT
    )
    assert record.goal_evaluation.observed_status is FirstSwingStatus.INDETERMINATE
    assert not record.goal_evaluation.achieved


def test_concept_scoring_and_pre_post_are_local_and_deterministic() -> None:
    case = _case("late-clearing-bracket")
    correct = (
        QuestionAnswer("accelerating_power", "a"),
        QuestionAnswer("first_swing_evidence", "b"),
    )
    incorrect = (
        QuestionAnswer("accelerating_power", "b"),
        QuestionAnswer("first_swing_evidence", "a"),
    )
    assert score_concept_answers(case, correct) == score_concept_answers(case, correct)

    record = run_guided_attempt(
        prepare_guided_attempt(case, "stable"),
        {"t_clear_s": 0.2},
        pre_answers=incorrect,
        post_answers=correct,
    )
    assert record.pre_post_score is not None
    assert (
        record.pre_post_score.pre_score.correct,
        record.pre_post_score.pre_score.total,
    ) == (0, 2)
    assert (
        record.pre_post_score.post_score.correct,
        record.pre_post_score.post_score.total,
    ) == (2, 2)
    assert record.pre_post_score.local_delta == 2
    limitation = record.pre_post_score.limitation.lower()
    assert "does not establish educational effectiveness" in limitation
    assert "student learned" not in limitation


def test_absent_pre_post_assessment_remains_not_assessed() -> None:
    record = run_guided_attempt(
        _prepare("controlled-inertia-effect"),
        {"H_s": 6.0},
    )

    assert record.pre_answers is None
    assert record.post_answers is None
    assert record.pre_post_score is None


def test_partial_concept_assessments_are_rejected() -> None:
    case = _case("late-clearing-bracket")
    partial = (QuestionAnswer("accelerating_power", "a"),)

    with pytest.raises(ValueError, match="complete assessment"):
        score_concept_answers(case, partial)
    with pytest.raises(ValueError, match="complete assessment"):
        run_guided_attempt(
            prepare_guided_attempt(case, "stable"),
            {"t_clear_s": 0.2},
            pre_answers=partial,
            post_answers=partial,
        )


@pytest.mark.parametrize(
    ("pre_answers", "post_answers"),
    (
        (
            (
                QuestionAnswer("accelerating_power", "a"),
                QuestionAnswer("first_swing_evidence", "b"),
            ),
            None,
        ),
        (
            None,
            (
                QuestionAnswer("accelerating_power", "a"),
                QuestionAnswer("first_swing_evidence", "b"),
            ),
        ),
    ),
)
def test_pre_and_post_assessments_must_be_supplied_together(
    pre_answers: tuple[QuestionAnswer, ...] | None,
    post_answers: tuple[QuestionAnswer, ...] | None,
) -> None:
    with pytest.raises(ValueError, match="supplied together"):
        run_guided_attempt(
            _prepare("controlled-inertia-effect"),
            {"H_s": 6.0},
            pre_answers=pre_answers,
            post_answers=post_answers,
        )


def test_repeated_attempt_is_exactly_deterministic() -> None:
    prepared = _prepare("controlled-inertia-effect", "smaller excursion")
    answers = (
        QuestionAnswer("accelerating_power", "a"),
        QuestionAnswer("first_swing_evidence", "b"),
    )

    first = run_guided_attempt(
        prepared,
        {"H_s": 6.0},
        hints_revealed=2,
        reveal_solution=True,
        pre_answers=answers,
        post_answers=answers,
    )
    second = run_guided_attempt(
        prepared,
        {"H_s": 6.0},
        hints_revealed=2,
        reveal_solution=True,
        pre_answers=answers,
        post_answers=answers,
    )

    assert first.case_id == second.case_id
    assert first.prediction == second.prediction
    assert first.changed_parameters == second.changed_parameters
    assert first.scientific_comparison == second.scientific_comparison
    assert first.goal_evaluation == second.goal_evaluation
    assert first.baseline_explanation == second.baseline_explanation
    assert first.attempted_explanation == second.attempted_explanation
    assert first.pre_post_score == second.pre_post_score
    for first_evaluation, second_evaluation in (
        (first.baseline_evaluation, second.baseline_evaluation),
        (first.attempted_evaluation, second.attempted_evaluation),
    ):
        assert first_evaluation.first_swing == second_evaluation.first_swing
        assert np.array_equal(
            first_evaluation.simulation.time_s,
            second_evaluation.simulation.time_s,
        )
        assert np.array_equal(
            first_evaluation.simulation.delta_rad,
            second_evaluation.simulation.delta_rad,
        )
        assert np.array_equal(
            first_evaluation.simulation.omega_dev_pu,
            second_evaluation.simulation.omega_dev_pu,
        )
    assert first.hints_revealed == prepared.guided_case.hints


def test_attempt_contract_contains_no_personal_or_nondeterministic_metadata() -> None:
    prohibited = {
        "student",
        "email",
        "ip",
        "machine_id",
        "timestamp",
        "uuid",
        "telemetry",
        "analytics",
    }

    assert prohibited.isdisjoint(field.name for field in fields(AttemptRecord))


def test_each_pedagogical_solution_produces_its_case_goal() -> None:
    for case in default_guided_cases():
        solution = case.pedagogical_solution
        assert solution is not None
        changes = {setting.key: setting.value for setting in solution.settings}
        record = run_guided_attempt(
            prepare_guided_attempt(case, case.prediction_options[0]),
            changes,
            reveal_solution=True,
        )

        assert record.goal_evaluation.achieved
        assert record.revealed_solution == solution
