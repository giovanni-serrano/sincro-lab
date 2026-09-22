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
    assert lesson["causal_story"][-1]["status"] == "indeterminate"
    assert "no permiten decidir" in lesson["causal_story"][-1]["text"]


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


@pytest.mark.parametrize("index", range(31))
def test_causal_story_copies_recorded_states_without_changing_verdict(index):
    run = portable.run_transient_lab(index, "unsure")
    lesson = phenomenon.explain_run(run)
    story = lesson["causal_story"]
    assert [step["id"] for step in story] == [
        "fault_balance", "acquired_motion", "clearing_continuity", "recovery",
    ]
    assert story[-1]["status"] == run.evaluation.first_swing.status
    times = run.evaluation.trajectory.time_s
    fault = times.index(run.evaluation.configuration.network.t_fault_s)
    clear = times.index(run.evaluation.configuration.network.t_clear_s)
    assert [point["index"] for point in story[1]["samples"]] == [fault, clear]
    assert run.cause[fault] in story[0]["text"]
    for step in story:
        for point in step["samples"]:
            i = point["index"]
            assert point == {
                "index": i, "time_s": times[i],
                "delta_rad": run.evaluation.trajectory.delta_rad[i],
                "omega_dev_pu": run.evaluation.trajectory.omega_dev_pu[i],
                "mechanical_power_pu": run.mechanical_power_pu[i],
                "electrical_power_pu": run.electrical_power_pu[i],
            }
    assert set(lesson["observation_cues"]) == set(run.network_state)
    assert all("dδ/dt" not in cue and "d(Δω)/dt" not in cue
               for cue in lesson["observation_cues"].values())


def test_teaching_projection_neither_simulates_nor_reclassifies(pair, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Teaching must consume the existing execution")
    monkeypatch.setattr(portable, "evaluate_transient", forbidden)
    monkeypatch.setattr(portable, "run_transient_lab", forbidden)
    a, b = pair
    assert phenomenon.explain_run(a)["causal_story"][-1]["status"] == "stable"
    assert phenomenon.explain_run(b)["causal_story"][-1]["status"] == "unstable"
    altered = replace(a, cause=tuple("Owner evidence" for _ in a.cause))
    assert "Owner evidence" in phenomenon.explain_run(altered)["causal_story"][0]["text"]


def test_clearing_explanation_does_not_assume_positive_speed(pair):
    run = pair[0]
    trajectory = run.evaluation.trajectory
    clear = trajectory.time_s.index(run.evaluation.configuration.network.t_clear_s)
    speed = list(trajectory.omega_dev_pu)
    speed[clear] = -0.001
    altered = replace(run, evaluation=replace(run.evaluation,
        trajectory=replace(trajectory, omega_dev_pu=tuple(speed))))
    story = phenomenon.explain_run(altered)["causal_story"]
    assert "no es positiva" in story[2]["text"]
    assert "incluido el amortiguamiento" in story[1]["text"]
    assert story[-1]["status"] == run.evaluation.first_swing.status


def test_canonical_causal_claims_match_independent_rhs_and_recorded_motion(pair):
    import numpy as np
    from sincrolab.models import SMIBParameters, smib_swing_rhs

    for run in pair:
        config = run.evaluation.configuration
        trajectory = run.evaluation.trajectory
        fault = trajectory.time_s.index(config.network.t_fault_s)
        clear = trajectory.time_s.index(config.network.t_clear_s)
        params = SMIBParameters(**{key: getattr(config.parameters, key)
            for key in ("H_s", "D_pu", "f_base_hz", "Pm_pu")})
        # RHS supplies acceleration including damping; narration is not the oracle.
        for i in range(fault, clear):
            derivative = smib_swing_rhs(trajectory.time_s[i],
                np.array([trajectory.delta_rad[i], trajectory.omega_dev_pu[i]]),
                params, Pmax_pu=config.network.Pmax_fault_pu)
            assert derivative[1] > 0
            assert run.electrical_power_pu[i] > 0  # This fault does not erase transfer.
        assert trajectory.omega_dev_pu[clear] > trajectory.omega_dev_pu[fault]
        # Prefault roundoff may put the fault sample just below zero; it must
        # not hide the observed positive gain by clearing.
        assert "más velocidad" in phenomenon.explain_run(run)["causal_story"][1]["text"]
    a, b = pair
    ac = phenomenon.explain_run(a)["clearing_index"]
    bc = phenomenon.explain_run(b)["clearing_index"]
    assert b.evaluation.trajectory.omega_dev_pu[bc] > a.evaluation.trajectory.omega_dev_pu[ac]
    assert b.angle_deg[bc] > a.angle_deg[ac]
    # The stable run still advances while decelerating after its clearing.
    params = SMIBParameters(**{key: getattr(a.evaluation.configuration.parameters, key)
        for key in ("H_s", "D_pu", "f_base_hz", "Pm_pu")})
    rhs = smib_swing_rhs(a.evaluation.trajectory.time_s[ac],
        np.array([a.evaluation.trajectory.delta_rad[ac], a.evaluation.trajectory.omega_dev_pu[ac]]),
        params, Pmax_pu=a.evaluation.configuration.network.Pmax_postfault_pu)
    assert rhs[0] > 0 and rhs[1] < 0
