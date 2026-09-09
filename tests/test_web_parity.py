"""Native four-surface parity; browser check consumes these same requests."""

from dataclasses import replace
import json
import subprocess
import sys

import pytest

from sincrolab.application import portable
from sincrolab.interfaces.desktop.adapter import DesktopController
from sincrolab.interfaces.web.bridge import dispatch


def cli(*arguments):
    completed = subprocess.run([sys.executable, "-m", "sincrolab.interfaces.cli", *arguments, "--json"], capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def guided_requests():
    result = []
    for summary in portable.list_guided_cases():
        case = portable.get_guided_case(summary.case_id)
        result.append(portable.GuidedAttemptRequest(case.case_id, case.prediction_options[0]))
    result.append(portable.GuidedAttemptRequest("controlled-inertia-effect", "smaller excursion", changes=(portable.ParameterValueDTO("H_s",6.0),)))
    return result


def free_configs():
    config = portable.get_guided_case(portable.list_guided_cases()[0].case_id).baseline_config
    return [replace(config, network=replace(config.network,t_clear_s=clear), t_end_s=end, dt_s=0.005)
        for clear,end in [(0.2,5.0),(0.35,5.0),(0.2,0.21)]]


def test_catalog_metadata_order_and_capabilities_across_native_surfaces():
    catalog = json.loads(portable.dumps_portable(portable.list_guided_cases()))
    assert cli("guided", "list") == dispatch("guided_list") == catalog
    assert cli("capabilities") == dispatch("capabilities") == portable.get_capabilities().to_dict()
    desktop = DesktopController()
    assert [case.case_id for case in desktop.catalog] == [case.case_id for case in portable.get_learning_content().cases]
    for item in catalog:
        case_id = item["case_id"]
        assert cli("guided","show",case_id) == dispatch("guided_show",{"case_id":case_id}) == portable.get_guided_case(case_id).to_dict()
        view = desktop.select_case(case_id)
        assert view.preview.title == item["title"]
        assert view.preview.objective == item["learning_objective"]
        assert view.preview.difficulty == next(term.label for term in portable.get_learning_content().meanings if term.key == item["difficulty"])
        assert desktop.case.to_dict() == portable.get_guided_case(case_id).to_dict()


@pytest.mark.parametrize("attempt_request", guided_requests(), ids=lambda r:r.case_id + ("-intervention" if r.changes else "-baseline"))
def test_canonical_guided_parity_including_cct_h24_changes_and_trajectories(attempt_request):
    expected = portable.run_guided_attempt(attempt_request).to_dict()
    desktop = DesktopController()
    desktop.select_case(attempt_request.case_id)
    desktop.set_changes({item.key:item.value for item in attempt_request.changes})
    desktop.prepare(attempt_request.prediction)
    actual = desktop.guided_job()()
    desktop.accept_guided(actual)
    arguments = ["guided", "run", attempt_request.case_id, "--prediction", attempt_request.prediction]
    for change in attempt_request.changes:
        arguments += ["--set", f"{change.key}={change.value}"]
    assert cli(*arguments) == actual.to_dict() == dispatch("guided_run",attempt_request.to_dict()) == expected
    assert expected["local_assessment"]["pre_score"] is None
    if attempt_request.case_id == "late-clearing-bracket":
        bracket = expected["critical_clearing_bracket"]
        assert bracket["stable_t_clear_s"] < bracket["unstable_t_clear_s"]
        assert bracket["time_tolerance_meaning"]
        assert "midpoint" not in bracket


@pytest.mark.parametrize("config,status", list(zip(free_configs(), ["stable","unstable","indeterminate"])))
def test_free_mode_native_parity(config, status):
    expected = portable.evaluate_transient(config).to_dict()
    desktop = DesktopController()
    job = desktop.prepare_free({"H_s":config.parameters.H_s, "t_clear_s":config.network.t_clear_s, "t_end_s":config.t_end_s, "dt_s":config.dt_s})
    assert job().to_dict() == dispatch("evaluate_transient",config.to_dict()) == expected
    assert expected["first_swing"]["status"] == status
    # H26 CLI has no arbitrary evaluate_transient command. Supported reference
    # invocations are compared below, without adding an API only for testing.


@pytest.mark.parametrize("case_id,dt_s", [("stable_transient",None),("unstable_transient",None),("adversarial_time_step",0.05)])
def test_cli_reference_canonical_status_and_series(case_id, dt_s):
    reference = portable.reproduce_reference_case(case_id, dt_s=dt_s)
    arguments = ["reference","run",case_id]
    if dt_s is not None:
        arguments += ["--dt-s",str(dt_s)]
    assert cli(*arguments) == reference.to_dict()
    assert dispatch("evaluate_transient",reference.evaluation.configuration.to_dict()) == reference.evaluation.to_dict()


def test_bridge_preserves_optional_complete_assessment_without_scoring():
    case_id = "controlled-inertia-effect"
    answers = tuple(portable.QuestionAnswerDTO(q.question_id,q.options[0].option_id) for q in portable.get_guided_case(case_id).conceptual_questions)
    attempt_request = replace(guided_requests()[-1],pre_answers=answers,post_answers=answers)
    expected = portable.run_guided_attempt(attempt_request).to_dict()
    assert dispatch("guided_run",attempt_request.to_dict()) == expected
    partial = replace(attempt_request,post_answers=None)
    with pytest.raises(ValueError,match="supplied together"):
        dispatch("guided_run",partial.to_dict())
