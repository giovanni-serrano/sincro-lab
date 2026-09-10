"""Scientific provenance and presentation contracts for the H30-C slice."""

from dataclasses import replace
import json
from math import asin, degrees, pi, sin, tau, trunc
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from sincrolab.application import portable
from sincrolab.interfaces.web.bridge import dispatch, dispatch_json

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def pair():
    lab = portable.get_transient_lab()
    return lab, portable.run_transient_lab(0, "unsure"), portable.run_transient_lab(len(lab.clearing_choices)-1, "lose")


def assert_blind_lab_discovery(payload):
    """Check the wire contract, including names that imply canonical outcomes."""
    assert set(payload) == {
        "schema_version", "baseline_config", "canonical_source", "projection_source",
        "clearing_choices", "initial_angle_deg", "prediction_options", "limitation",
    }
    assert len(payload["clearing_choices"]) == 31
    assert all(set(choice) == {"schema_version", "t_clear_s", "fault_duration_s"}
               for choice in payload["clearing_choices"])
    encoded = json.dumps(payload, ensure_ascii=False).casefold()
    # Derive forbidden names from the real catalog, so renaming a reference
    # does not silently disable the semantic leakage regression.
    for summary in portable.list_reference_cases():
        reference = portable.get_reference_case(summary.case_id)
        assert reference.case_id.casefold() not in encoded
        if reference.input_case_file:
            assert reference.input_case_file.casefold() not in encoded
    for forbidden in ("early_reference_id", "late_reference_id", "input_case_files",
                      "expected_observations", "first_swing", "trajectory", "stable_duration",
                      "stable_transient", "unstable_transient",
                      "stable_transient_smib.json", "unstable_transient_smib.json"):
        assert forbidden not in encoded


def test_discovery_uses_existing_sources_without_simulation_or_answer_keys(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Discovery must not execute a simulation")
    monkeypatch.setattr(portable, "evaluate_transient", forbidden)
    lab = dispatch("transient_lab")
    assert_blind_lab_discovery(lab)
    assert lab == portable.get_transient_lab().to_dict()
    assert json.loads(dispatch_json("transient_lab"))["data"] == lab
    assert lab["canonical_source"] == "reference_cases/smib_v0_1_golden_cases.json"
    assert len(lab["clearing_choices"]) == 31


def test_pair_provenance_matches_public_input_files_and_only_clearing_changes(pair):
    lab, early, late = pair
    for run, case_id in [(early, "stable_transient"), (late, "unstable_transient")]:
        config = run.evaluation.configuration
        source = json.loads((ROOT / "reference_cases" / run.source_case_file).read_text())
        assert run.reference_id == case_id and run.changed_fields == ()
        assert run.projection_source == "sincrolab.application/_h23_reference_projection.json"
        for owner, key in [(config.parameters,"smib_parameters"),(config.network,"transient_network")]:
            assert {k:v for k,v in owner.to_dict().items() if k != "schema_version"} == source[key]
        for key,value in source["simulation"].items():
            assert getattr(config,key) == value
        assert config.initial_state.delta_rad == asin(0.7/1.2)
        assert config.initial_state.omega_dev_pu == 0
        assert run.evaluation == portable.reproduce_reference_case(case_id).evaluation
    a,b = early.evaluation.configuration,late.evaluation.configuration
    assert replace(a,network=replace(a.network,t_clear_s=b.network.t_clear_s)) == b
    assert early.fault_duration_s == pytest.approx(a.network.t_clear_s-a.network.t_fault_s)
    assert late.fault_duration_s == pytest.approx(b.network.t_clear_s-b.network.t_fault_s)


def test_real_outcomes_and_sample_evidence(pair):
    _, early, late = pair
    assert early.evaluation.first_swing.status == "stable"
    assert late.evaluation.first_swing.status == "unstable"
    first_max = max(early.evaluation.trajectory.delta_rad)
    assert first_max < pi-asin(0.7/1.1)
    assert min(early.evaluation.trajectory.omega_dev_pu) < 0
    assert late.evaluation.trajectory.delta_rad[-1] > 2*pi
    assert all(speed > 0 for speed in late.evaluation.trajectory.omega_dev_pu[21:])


def test_independent_segmented_scipy_oracle(pair):
    for run in pair[1:]:
        config = run.evaluation.configuration
        samples = run.evaluation.trajectory
        expected = np.empty((len(samples.time_s),2))
        state = np.array([asin(0.7/1.2),0.0])
        for left,right,limit in [(0,0.1,1.2),(0.1,config.network.t_clear_s,0.2),(config.network.t_clear_s,5,1.1)]:
            def rhs(t,y):
                return [2*pi*60*y[1], (0.7-limit*sin(y[0])-0.2*y[1])/7]
            solution = solve_ivp(rhs,(left,right),state,method="DOP853",rtol=1e-12,atol=1e-14,dense_output=True)
            assert solution.success
            indices = np.where((np.array(samples.time_s)>=left)&(np.array(samples.time_s)<=right))[0]
            expected[indices] = solution.sol(np.array(samples.time_s)[indices]).T
            state = solution.y[:,-1]
        # H30-C retains the accepted dt; long unstable trajectories amplify
        # numerical error. This bound checks the full trajectory, not a label.
        assert np.max(np.abs(expected[:,0]-samples.delta_rad)) < 0.002
        assert np.max(np.abs(expected[:,1]-samples.omega_dev_pu)) < 0.0001


def test_power_projection_events_and_continuous_angle_are_exact(pair):
    for run in pair[1:]:
        data = run.evaluation.trajectory
        config = run.evaluation.configuration
        assert len(set(map(len,[run.playhead_time_s,run.angle_deg,run.relative_turns,run.network_state,run.electrical_power_pu,run.cause,data.time_s]))) == 1
        assert np.all(np.diff(data.time_s)>0)
        assert run.angle_deg == tuple(map(degrees,data.delta_rad))
        assert run.relative_turns == tuple(trunc((v-data.delta_rad[0])/tau) for v in data.delta_rad)
        for index,t in enumerate(data.time_s):
            expected_state = "prefault" if t<0.1 else "fault" if t<config.network.t_clear_s else "postfault"
            assert run.network_state[index] == expected_state
            pmax = {"prefault":1.2,"fault":0.2,"postfault":1.1}[expected_state]
            assert run.electrical_power_pu[index] == pmax*sin(data.delta_rad[index])
            assert run.mechanical_power_pu[index] == 0.7
            assert run.power_imbalance_pu[index] == 0.7-run.electrical_power_pu[index]
        assert data.time_s.count(0.1) == 1
        assert data.time_s.count(config.network.t_clear_s) == 1


def test_comparison_alignment_preserves_identical_history_and_real_divergence(pair):
    _, a,b = pair
    assert a.playhead_time_s == b.playhead_time_s
    np.testing.assert_allclose(a.evaluation.trajectory.time_s,b.evaluation.trajectory.time_s,rtol=0,atol=2e-15)
    clear = a.evaluation.configuration.network.t_clear_s
    boundary = a.playhead_time_s.index(clear)
    np.testing.assert_allclose(a.angle_deg[:boundary+1],b.angle_deg[:boundary+1],rtol=0,atol=1e-12)
    np.testing.assert_allclose(a.evaluation.trajectory.omega_dev_pu[:boundary+1],b.evaluation.trajectory.omega_dev_pu[:boundary+1],rtol=0,atol=1e-15)
    assert a.network_state[boundary] == "postfault" and b.network_state[boundary] == "fault"
    assert a.electrical_power_pu[boundary] > b.electrical_power_pu[boundary]
    assert a.angle_deg[boundary+1] < b.angle_deg[boundary+1]


@pytest.mark.parametrize("choice", range(31))
def test_every_permitted_duration_preserves_grid_and_other_inputs(choice,pair):
    lab,early,_ = pair
    run = portable.run_transient_lab(choice,"unsure")
    config = run.evaluation.configuration
    expected = replace(lab.baseline_config,network=replace(lab.baseline_config.network,t_clear_s=lab.clearing_choices[choice].t_clear_s))
    assert config == expected
    assert run.playhead_time_s == early.playhead_time_s
    assert run.changed_fields == (() if choice in (0,30) else ("network.t_clear_s",))


@pytest.mark.parametrize("index,prediction", [(-1,"unsure"),(31,"lose"),(True,"lose"),(1.5,"unsure"),(0,""),(0,None),(0,"stable")])
def test_invalid_choices_and_missing_predictions_fail_before_execution(monkeypatch,index,prediction):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid inputs must not execute science")
    monkeypatch.setattr(portable,"evaluate_transient",forbidden)
    response = json.loads(dispatch_json("transient_lab_run",json.dumps({"clearing_choice_index":index,"prediction":prediction})))
    assert not response["ok"] and response["error"]["kind"] == "invalid_input"
    assert "data" not in response


def test_bridge_rejects_extra_parameters_and_preserves_projection(pair):
    payload = {"clearing_choice_index":0,"prediction":"unsure"}
    assert dispatch("transient_lab_run",payload) == pair[1].to_dict()
    with pytest.raises(ValueError,match="Unexpected"):
        dispatch("transient_lab_run",{**payload,"H_s":6})


def test_indeterminate_is_preserved_from_real_short_horizon(monkeypatch,pair):
    lab,_,_ = pair
    short = replace(lab.baseline_config,t_end_s=0.21)
    evaluation = portable.evaluate_transient(short)
    assert evaluation.first_swing.status == "indeterminate"
    monkeypatch.setattr(portable,"evaluate_transient",lambda _: evaluation)
    run = dispatch("transient_lab_run",{"clearing_choice_index":0,"prediction":"unsure"})
    assert run["evaluation"]["first_swing"]["status"] == "indeterminate"
    assert run["evaluation"] == evaluation.to_dict()


def test_frontend_uses_projection_without_science_or_result_thresholds():
    source = (ROOT / "web/transient-lab.js").read_text(encoding="utf-8")
    for forbidden in ("Math.sin", "Math.cos", "Math.PI", "Math.asin", "delta_rad >", "angle > 180", "classical_rk4", "Pm_pu -", "localStorage", "fetch("):
        assert forbidden not in source
    assert "outcomes[item.evaluation.first_swing.status]" in source
    assert 'indeterminate:"Resultado indeterminado"' in source
    assert "item?.angle_deg[index]" in source


def test_prefault_roundoff_is_not_described_as_a_disturbance(pair):
    for run in pair[1:]:
        for index,time in enumerate(run.evaluation.trajectory.time_s):
            if time < run.evaluation.configuration.network.t_fault_s:
                assert "equilibrio" in run.cause[index]
                assert "supera" not in run.cause[index]


def test_projection_rejects_off_grid_samples_instead_of_resampling(pair):
    lab,_,_ = pair
    evaluation = portable.evaluate_transient(replace(lab.baseline_config,t_end_s=0.212))
    with pytest.raises(RuntimeError,match="time grid"):
        portable._transient_lab_projection(evaluation,lab,0,"unsure")


@pytest.mark.parametrize("leaked_value", [
    "stable_transient", "unstable_transient", "stable_transient_smib.json",
    "unstable_transient_smib.json",
])
def test_discovery_guard_rejects_outcome_names_in_neutral_metadata(leaked_value):
    payload = dispatch("transient_lab")
    payload["limitation"] = leaked_value
    with pytest.raises(AssertionError):
        assert_blind_lab_discovery(payload)
