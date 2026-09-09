"""H28 controller integration through the real H26 facade, without Qt."""

from dataclasses import replace

import pytest

import sincrolab.application.portable as portable
from sincrolab.interfaces.desktop.adapter import DesktopController


def controller(case_id="controlled-inertia-effect"):
    value = DesktopController()
    value.select_case(case_id)
    return value


def execute(value, prediction=None, pre=None):
    value.prepare(prediction or value.case.prediction_options[0], pre)
    result = value.guided_job()()
    value.accept_guided(result)
    return result


def test_catalog_and_prediction_options_have_one_portable_owner():
    value = DesktopController()
    assert [item.case_id for item in value.catalog] == [
        item.case_id for item in portable.get_learning_content().cases
    ]
    for preview in value.catalog:
        view = value.select_case(preview.case_id)
        source = portable.get_guided_case(preview.case_id)
        assert view.preview.title == source.title
        assert view.preview.objective == source.learning_objective
        assert view.prediction_options == source.prediction_options
        assert [(item.key, item.minimum, item.maximum) for item in view.fields] == [
            (item.key, item.minimum, item.maximum) for item in source.editable_parameters
        ]
        assert value.result is None
        assert value.solution is None
        assert value.hints == ()


@pytest.mark.parametrize("prediction", [None, "", "incorrect", "STABLE"])
def test_unanswered_or_invalid_prediction_never_executes(monkeypatch, prediction):
    value = controller("first-swing-event-evidence")
    def forbidden(request):
        pytest.fail("Execution occurred before a valid prediction")
    monkeypatch.setattr(portable, "run_guided_attempt", forbidden)
    with pytest.raises(ValueError, match="predicción"):
        value.prepare(prediction)
    with pytest.raises(ValueError, match="predicción"):
        value.guided_job()
    assert value.result is None
    assert value.history == []


@pytest.mark.parametrize("case_id", [
    "late-clearing-bracket", "controlled-inertia-effect", "first-swing-event-evidence",
])
def test_real_guided_baseline_intervention_comparison_explanation_and_hints(case_id, monkeypatch):
    value = controller(case_id)
    requests = []
    original = portable.run_guided_attempt
    def traced(request):
        requests.append(request)
        return original(request)
    monkeypatch.setattr(portable, "run_guided_attempt", traced)
    first = execute(value)
    assert first.changed_parameters == ()
    assert first.baseline_evaluation == first.attempted_evaluation
    assert first.local_assessment == portable.LocalAssessmentDTO(False, None, None, None, None)
    assert value.phase == "Simular"
    value.go_to("Intervenir")
    value.reveal_hint()
    assert value.hints == portable.get_guided_hints(case_id, 1).hints
    assert value.solution is None
    value.reveal_hint()
    assert value.hints == portable.get_guided_hints(case_id, 2).hints
    value.reveal_solution()
    assert value.prediction is None
    assert value.request is None
    assert value.phase == "Predecir"
    result = execute(value)
    assert result == original(requests[-1])
    assert result.goal_evaluation.achieved
    assert result.solution_revealed
    assert result.baseline_config == first.baseline_config
    assert result.baseline_evaluation == first.baseline_evaluation
    assert result.scientific_comparison.baseline_status == first.baseline_evaluation.first_swing.status
    view = value.result_view()
    assert view.status == result.attempted_evaluation.first_swing.status
    assert view.reason == result.attempted_evaluation.first_swing.reason
    assert view.curves[0].delta_rad is result.baseline_evaluation.trajectory.delta_rad
    assert view.curves[1].omega_dev_pu is result.attempted_evaluation.trajectory.omega_dev_pu
    assert result.attempted_evaluation.explanation.summary in view.explanation
    assert result.debrief_summary in view.debrief
    assert view.changes[0][0].startswith(source_quantity(result.changed_parameters[0].key).label)
    assert len(value.history) == 2
    assert value.phase == "Comparar"
    if case_id == "controlled-inertia-effect":
        assert [item.key for item in result.changed_parameters] == ["H_s"]
        assert result.attempted_config.network == result.baseline_config.network
        assert result.attempted_config.initial_state == result.baseline_config.initial_state
    if case_id == "late-clearing-bracket":
        bracket = result.critical_clearing_bracket
        assert bracket.stable_t_clear_s < bracket.unstable_t_clear_s
        assert "criterio de parada" in view.clearing
        assert result.critical_clearing_explanation.summary in view.clearing
        assert "midpoint" not in bracket.to_dict()


@pytest.mark.parametrize("changes", [
    {"Pm_pu": "0.8"}, {"H_s": "NaN"}, {"H_s": "inf"}, {"H_s": "x"},
    {"H_s": "1.9"}, {"H_s": "8.1"},
])
def test_intervention_rejects_unknown_invalid_and_out_of_contract_inputs(changes):
    value = controller()
    with pytest.raises(ValueError):
        value.set_changes(changes)
    assert value.changes == {}
    assert value.result is None


def test_structured_changes_reset_prediction_and_preserve_baseline():
    value = controller()
    first = execute(value, "no change")
    value.set_changes({"H_s": "6"})
    assert value.changes == {"H_s": 6.0}
    assert value.prediction is None
    result = execute(value, "smaller excursion")
    assert result.changed_parameters == (portable.ParameterChangeDTO("H_s", 3.5, 6.0, "s"),)
    assert result.baseline_config == first.baseline_config
    assert value.result_view().comparison[2][1:] == (
        format(result.scientific_comparison.baseline_max_delta_rad, ".12g"),
        format(result.scientific_comparison.attempted_max_delta_rad, ".12g"),
    )


def test_same_case_resumes_and_new_case_clears_session_without_unknown_case_mutation():
    value = controller()
    execute(value)
    value.reveal_hint()
    old = value.result
    value.select_case(value.case.case_id)
    assert value.result is old
    with pytest.raises(ValueError):
        value.select_case("missing")
    assert value.result is old
    value.select_case("first-swing-event-evidence")
    assert value.phase == "Observar"
    assert value.history == []
    assert value.result is value.request is value.completed_request is None
    assert value.prediction is value.pre_answers is value.completed_pre_answers is None
    assert value.changes == {} and value.hints == () and value.solution is None


def test_pre_post_is_complete_optional_and_scored_only_by_existing_workflow(monkeypatch):
    value = controller()
    with pytest.raises(ValueError, match="Completa"):
        value.prepare("no change", {"accelerating_power": "a"})
    pre = {"accelerating_power": "b", "first_swing_evidence": "b"}
    first = execute(value, "no change", pre)
    assert not first.local_assessment.assessed
    assert first.pre_answers is first.post_answers is None
    with pytest.raises(ValueError, match="Completa"):
        value.assessment_job({})
    request = value.completed_request
    post = {"accelerating_power": "a", "first_swing_evidence": "b"}
    job = value.assessment_job(post)
    assert job.args[0] == replace(
        request,
        pre_answers=(portable.QuestionAnswerDTO("accelerating_power", "b"),
                     portable.QuestionAnswerDTO("first_swing_evidence", "b")),
        post_answers=(portable.QuestionAnswerDTO("accelerating_power", "a"),
                      portable.QuestionAnswerDTO("first_swing_evidence", "b")),
    )
    assessed = job()
    value.accept_guided(assessed, assessment=True)
    assert assessed.local_assessment.pre_score.correct == 1
    assert assessed.local_assessment.post_score.correct == 2
    assert assessed.local_assessment.local_delta == 1
    assert assessed.baseline_evaluation == first.baseline_evaluation
    assert assessed.attempted_evaluation == first.attempted_evaluation
    assert len(value.history) == 1
    assert value.phase == "Explicar"
    assert value.history[0] is assessed


def test_failed_next_request_does_not_replace_completed_assessment_request():
    value = controller()
    pre = {"accelerating_power": "b", "first_swing_evidence": "b"}
    first = execute(value, "no change", pre)
    value.set_changes({"H_s": 6})
    value.prepare("smaller excursion")
    job = value.assessment_job(pre)
    assert job.args[0].changes == ()
    assert job.args[0].prediction == first.prediction


@pytest.mark.parametrize(("clear", "end", "status"), [
    ("0.2", "5", "stable"), ("0.35", "5", "unstable"),
    ("0.2", "0.21", "indeterminate"),
])
def test_free_mode_uses_real_portable_and_preserves_all_three_outcomes(clear, end, status):
    value = DesktopController()
    job = value.prepare_free({"H_s": "3.5", "t_clear_s": clear, "t_end_s": end, "dt_s": "0.005"})
    assert job.func is portable.evaluate_transient
    result = job()
    assert result == portable.evaluate_transient(job.args[0])
    value.accept_free(result)
    view = value.free_result_view()
    assert view.status == status == result.first_swing.status
    assert view.reason == result.first_swing.reason
    assert view.curves[0].delta_rad is result.trajectory.delta_rad
    assert result.explanation.summary in view.explanation


@pytest.mark.parametrize(("key", "invalid"), [("H_s", "0"), ("dt_s", "-1"), ("t_clear_s", "0.01")])
def test_free_domain_rejection_is_not_a_scientific_status(key, invalid):
    value = DesktopController()
    inputs = {"H_s": "3.5", "t_clear_s": "0.2", "t_end_s": "5", "dt_s": "0.005"}
    inputs[key] = invalid
    with pytest.raises(ValueError):
        value.prepare_free(inputs)()
    assert value.free_result is None


def test_navigation_cannot_reveal_result_before_prediction_and_execution():
    value = controller()
    for phase in ("Simular", "Intervenir", "Comparar", "Explicar"):
        with pytest.raises(ValueError, match="predicción"):
            value.go_to(phase)
    value.go_to("Predecir")
    assert value.result_view() is None


def source_quantity(key):
    return next(item for item in portable.get_learning_content().quantities if item.key == key)
