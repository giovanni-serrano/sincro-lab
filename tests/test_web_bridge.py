"""H29 JSON boundary tests; scientific results come from the real H26 path."""

import ast
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sincrolab.application import portable
from sincrolab.interfaces.web.bridge import dispatch, dispatch_json


ROOT = Path(__file__).parents[1]


def request(case_id="controlled-inertia-effect", **changes):
    case = portable.get_guided_case(case_id)
    return portable.GuidedAttemptRequest(case_id, case.prediction_options[0],
        changes=tuple(portable.ParameterValueDTO(k, v) for k, v in changes.items()))


def test_bridge_catalog_and_detail_are_canonical_without_spoilers():
    catalog = dispatch("guided_list")
    assert catalog == json.loads(portable.dumps_portable(portable.list_guided_cases()))
    for summary in catalog:
        detail = dispatch("guided_show", {"case_id": summary["case_id"]})
        assert detail == portable.get_guided_case(summary["case_id"]).to_dict()
        encoded = json.dumps(detail)
        for forbidden in ("correct_option_id", '"hints":', '"settings":', '"expected_observations":'):
            assert forbidden not in encoded
    assert dispatch("capabilities") == portable.get_capabilities().to_dict()


def test_hints_and_solution_are_explicit_separate_calls():
    case_id = "late-clearing-bracket"
    first = dispatch("guided_hints", {"case_id":case_id, "count":1})
    second = dispatch("guided_hints", {"case_id":case_id, "count":2})
    assert first == portable.get_guided_hints(case_id, 1).to_dict()
    assert second["hints"][:1] == first["hints"]
    assert dispatch("guided_solution", {"case_id":case_id}) == portable.get_guided_solution(case_id).to_dict()


@pytest.mark.parametrize("prediction", [None, "", "invented", "STABLE"])
def test_prediction_is_required_before_h25_execution(monkeypatch, prediction):
    import sincrolab.application.guided_learning as learning
    def forbidden(*args, **kwargs):
        pytest.fail("Scientific execution must not occur without a valid prediction")
    monkeypatch.setattr(portable, "run_h25_guided_attempt", forbidden)
    data = request().to_dict()
    data["prediction"] = prediction
    result = json.loads(dispatch_json("guided_run", json.dumps(data)))
    assert not result["ok"] and result["error"]["kind"] == "invalid_input"
    assert "data" not in result
    assert learning.prepare_guided_attempt is portable.prepare_guided_attempt


@pytest.mark.parametrize("changes", [{"H_s":100}, {"Pm_pu":0.8}, {"t_clear_s":0.2}])
def test_guided_constraints_are_validated_by_portable(changes):
    with pytest.raises(ValueError):
        dispatch("guided_run", request(**changes).to_dict())


def test_every_new_request_requires_prediction_and_preserves_old_result():
    first = dispatch("guided_run", request().to_dict())
    next_request = request(H_s=6).to_dict()
    del next_request["prediction"]
    with pytest.raises(TypeError):
        dispatch("guided_run", next_request)
    second = dispatch("guided_run", request(H_s=6).to_dict())
    assert second["baseline_evaluation"] == first["baseline_evaluation"]
    assert [change["key"] for change in second["changed_parameters"]] == ["H_s"]
    assert second["local_assessment"] == portable.LocalAssessmentDTO(False, None, None, None, None).to_dict()


@pytest.mark.parametrize("clear,end,status", [(0.2,5,"stable"), (0.35,5,"unstable"), (0.2,0.21,"indeterminate")])
def test_free_mode_preserves_entire_real_payload(clear, end, status):
    config = portable.get_guided_case(portable.list_guided_cases()[0].case_id).baseline_config
    config = replace(config, network=replace(config.network,t_clear_s=clear), t_end_s=end)
    result = dispatch("evaluate_transient", config.to_dict())
    assert result == portable.evaluate_transient(config).to_dict()
    assert result["first_swing"]["status"] == status


@pytest.mark.parametrize("field,value", [("dt_s",-1), ("dt_s",True), ("t_end_s","5"), ("schema_version",2)])
def test_invalid_config_is_error_not_a_scientific_outcome(field, value):
    config = portable.get_guided_case("first-swing-event-evidence").baseline_config.to_dict()
    config[field] = value
    envelope = json.loads(dispatch_json("evaluate_transient", json.dumps(config)))
    assert envelope["ok"] is False and "data" not in envelope
    assert envelope["error"]["kind"] == "invalid_input"


def test_unexpected_and_portable_errors_are_separate(monkeypatch):
    for error, kind in [(RuntimeError("invariant"), "portable_error"), (ArithmeticError("failure"), "unexpected")]:
        def fail():
            raise error
        monkeypatch.setattr(portable, "get_capabilities", fail)
        response = json.loads(dispatch_json("capabilities"))
        assert response["error"]["kind"] == kind
        assert "data" not in response
    assert not json.loads(dispatch_json("anything"))["ok"]
    assert not json.loads(dispatch_json("guided_run", "not json"))["ok"]


def test_bridge_is_the_only_web_boundary_and_has_no_scientific_arithmetic():
    directory = ROOT / "src/sincrolab/interfaces/web"
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.AugAssign)):
                pytest.fail(f"Review scientific arithmetic introduced in {path.name}")
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            for name in imports:
                if name.startswith("sincrolab"):
                    assert path.name == "bridge.py"
                    assert name == "sincrolab.application.portable"
                assert name.split(".")[0] not in {"numpy", "scipy", "PySide6", "matplotlib"}


def test_bridge_import_does_not_load_qt_scipy_or_desktop():
    completed = subprocess.run([sys.executable, "-c", "from sincrolab.interfaces.web.bridge import dispatch; import sys; dispatch('guided_list'); assert not any(k.split('.')[0] in {'PySide6','scipy'} or k.startswith('sincrolab.interfaces.desktop') for k in sys.modules)"], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
