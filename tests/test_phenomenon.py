"""Contracts for the beginner teaching adapter; physical owners stay unchanged."""
from dataclasses import replace
import json

import pytest

from sincrolab.application import phenomenon, portable
from sincrolab.interfaces.web.bridge import dispatch, dispatch_json


@pytest.fixture(scope="module")
def pair():
    return [portable.run_transient_lab(index, "unsure") for index in (0, 30)]


@pytest.mark.parametrize("index", [0, 15, 30])
def test_lesson_preserves_every_portable_value(index):
    actual = dispatch("phenomenon_run", {"clearing_choice_index": index, "prediction": "lose"})
    expected = portable.run_transient_lab(index, "lose")
    assert actual["run"] == expected.to_dict()
    lesson = actual["lesson"]
    end = lesson["first_swing_end_index"]
    assert 0 < end < len(expected.angle_deg) - 1
    assert expected.evaluation.trajectory.time_s[end] >= lesson["event_bracket"]["right_time_s"] + 0.15
    assert expected.evaluation.trajectory.time_s[lesson["clearing_index"]] == expected.evaluation.configuration.network.t_clear_s
    assert lesson["prediction"] == "Perderá sincronismo"


@pytest.mark.parametrize("prediction", ["", None, "stable"])
def test_prediction_is_required_before_any_execution(monkeypatch, prediction):
    def forbidden(*args, **kwargs):
        pytest.fail("No simulation before a valid prediction")
    monkeypatch.setattr(portable, "evaluate_transient", forbidden)
    result = json.loads(dispatch_json("phenomenon_run", json.dumps({"clearing_choice_index": 0, "prediction": prediction})))
    assert result["error"]["kind"] == "invalid_input"
    assert "data" not in result


def test_transfer_is_unseen_and_blind_without_execution(monkeypatch):
    monkeypatch.setattr(portable, "evaluate_transient", lambda *_: pytest.fail("No transfer precomputation"))
    used = [0, 30]
    first = dispatch("phenomenon_transfer", {"used_choice_indices": used})
    assert set(first) == {"choice_index", "prompt"}
    assert first["choice_index"] not in used
    assert first["choice_index"] == 15
    for word in ("stable", "unstable", "inestable", "solution", "answer", "reference_id"):
        assert word not in json.dumps(first)
    for _ in range(29):
        choice = portable.prepare_phenomenon_transfer(used)["choice_index"]
        assert choice not in used and 0 < choice < 30
        used.append(choice)
    assert portable.prepare_phenomenon_transfer(used)["choice_index"] is None


@pytest.mark.parametrize("used", [None, "0", [True], [-1], [31], [1.5]])
def test_transfer_rejects_invalid_input(used):
    with pytest.raises(ValueError):
        portable.prepare_phenomenon_transfer(used)


def test_window_and_evidence_are_classifier_samples(pair):
    for run in pair:
        lesson = phenomenon.explain_run(run)
        event = run.evaluation.first_swing
        bracket = event.reversal_bracket or event.crossing_bracket
        assert lesson["event_bracket"] == bracket.to_dict()
        assert lesson["first_swing_end_index"] > bracket.right_index
        assert f"{bracket.left_time_s:.3f}" in lesson["evidence"]
        assert f"{bracket.right_time_s:.3f}" in lesson["evidence"]
    # Shared original-angle scale over the combined window makes the returning
    # excursion occupy a substantial vertical span, unlike the 5 s horizon.
    end = max(phenomenon.explain_run(run)["first_swing_end_index"] for run in pair)
    a, b = (run.angle_deg[:end + 1] for run in pair)
    assert (max(a) - min(a)) / (max(*a, *b) - min(*a, *b)) > 0.15


def test_prediction_confrontation_uses_the_existing_classification(pair):
    a, b = pair
    assert "coincide" in phenomenon.explain_run(replace(a, prediction="maintain"))["confrontation"]
    assert "difiere" in phenomenon.explain_run(replace(b, prediction="maintain"))["confrontation"]
    assert "evidencia" in phenomenon.explain_run(a)["confrontation"]


def test_real_indeterminate_is_not_reclassified(monkeypatch):
    lab = portable.get_transient_lab()
    short = portable.evaluate_transient(replace(lab.baseline_config, t_end_s=0.21))
    monkeypatch.setattr(portable, "evaluate_transient", lambda _: short)
    response = portable.run_phenomenon(0, "maintain")
    assert response["run"]["evaluation"]["first_swing"]["status"] == "indeterminate"
    lesson = response["lesson"]
    assert lesson["event_bracket"] is None
    assert lesson["first_swing_end_index"] == len(short.trajectory.time_s) - 1
    assert "no permite" in lesson["outcome"]
    assert "confirmar ni descartar" in lesson["confrontation"]


def test_formalization_defers_equations_and_preserves_damping(pair):
    stages = phenomenon.explain_run(pair[0])["stages"]
    assert [stage["id"] for stage in stages] == ["physical", "powers", "balance", "speed", "angle", "equations"]
    assert all("dδ/dt" not in stage["text"] and "d(Δω)/dt" not in stage["text"] for stage in stages[:-1])
    assert "Pm" not in stages[0]["text"] and "Pa" not in stages[1]["text"]
    assert "amortiguamiento" in stages[2]["text"]
    assert "D·Δω" in stages[-1]["text"] and "radianes" in stages[-1]["text"]


def test_new_bridge_operations_reject_extra_configuration():
    for operation, payload in [
        ("phenomenon_run", {"clearing_choice_index": 0, "prediction": "unsure", "H_s": 6}),
        ("phenomenon_transfer", {"used_choice_indices": [], "prediction": "lose"}),
    ]:
        with pytest.raises(ValueError, match="Unexpected"):
            dispatch(operation, payload)
