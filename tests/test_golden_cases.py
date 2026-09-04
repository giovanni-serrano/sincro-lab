import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sincrolab.analysis import FirstSwingStatus, assess_smib_first_swing
from sincrolab.application import (
    cross_check_smib_critical_clearing,
    simulate_smib_transient,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


REFERENCE_CASES = Path(__file__).parents[1] / "reference_cases"
GOLDEN_CASE_PATH = REFERENCE_CASES / "smib_v0_1_golden_cases.json"
EVIDENCE_TYPES = {
    "ANALYTIC_ORACLE",
    "EXTERNAL_NUMERICAL_ORACLE",
    "CROSS_CHECKED_EVIDENCE",
    "ACCEPTED_REGRESSION",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_inputs(
    case: Mapping[str, Any],
) -> tuple[SMIBParameters, SMIBTransientNetwork, SMIBInitialState]:
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    return parameters, network, initial_state


def _input_case(golden_case: Mapping[str, Any]) -> dict[str, Any]:
    return _load_json(REFERENCE_CASES / golden_case["input_case_file"])


def _expectations(
    expected_observations: Mapping[str, Any],
) -> Iterator[Mapping[str, Any]]:
    for expectation in expected_observations.values():
        if isinstance(expectation, list):
            yield from expectation
        else:
            yield expectation


def _assert_no_trajectory_arrays(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            assert not (
                key in {"time_s", "delta_rad", "omega_dev_pu"}
                and isinstance(child, list)
            )
            _assert_no_trajectory_arrays(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_trajectory_arrays(child)


def test_golden_collection_has_explicit_provenance_and_no_trajectories() -> None:
    collection = _load_json(GOLDEN_CASE_PATH)
    serialized_collection = json.dumps(collection)

    assert collection["schema_version"] == 1
    assert collection["collection_id"] == "smib_v0_1_golden_cases"
    assert collection["metadata"]["represents_specific_real_system"] is False
    assert set(collection["metadata"]["evidence_types"]) == EVIDENCE_TYPES
    assert "oracle_type" not in serialized_collection
    assert set(collection["cases"]) == {
        "stable_transient",
        "unstable_transient",
        "adversarial_time_step",
        "classic_undamped",
        "scipy_cross_checked_transient",
    }

    for case in collection["cases"].values():
        assert case["purpose"]
        assert case["limitations"]
        for expectation in _expectations(case["expected_observations"]):
            assert expectation["evidence_type"] in EVIDENCE_TYPES
            assert expectation["provenance"]
            assert "comparison" in expectation or any(
                key.startswith(("abs_tolerance_", "upper_bound_"))
                for key in expectation
            )

    for case_name in (
        "stable_transient",
        "unstable_transient",
        "adversarial_time_step",
    ):
        input_path = REFERENCE_CASES / collection["cases"][case_name][
            "input_case_file"
        ]
        assert input_path.is_file()

    _assert_no_trajectory_arrays(collection)


@pytest.mark.parametrize(
    "golden_case_name",
    ["stable_transient", "unstable_transient"],
)
def test_transient_golden_case_preserves_scientific_observations(
    golden_case_name: str,
) -> None:
    golden_case = _load_json(GOLDEN_CASE_PATH)["cases"][golden_case_name]
    input_case = _input_case(golden_case)
    parameters, network, initial_state = _build_inputs(input_case)
    simulation_config = input_case["simulation"]
    expected = golden_case["expected_observations"]

    selected_results = []
    for _ in range(2):
        result = simulate_smib_transient(
            parameters,
            initial_state,
            network,
            t_start_s=simulation_config["t_start_s"],
            t_end_s=simulation_config["t_end_s"],
            dt_s=simulation_config["dt_s"],
        )
        assessment = assess_smib_first_swing(result)
        fault_index = int(
            np.flatnonzero(result.time_s == network.t_fault_s)[0]
        )
        clear_index = int(
            np.flatnonzero(result.time_s == network.t_clear_s)[0]
        )
        fault_acceleration_pu_per_s = float(
            smib_swing_rhs(
                network.t_fault_s,
                np.array(
                    [
                        result.delta_rad[fault_index],
                        result.omega_dev_pu[fault_index],
                    ]
                ),
                parameters,
                Pmax_pu=network.Pmax_fault_pu,
            )[1]
        )

        assert np.count_nonzero(result.time_s == network.t_fault_s) == (
            expected["fault_event_occurrences"]["value"]
        )
        assert np.count_nonzero(result.time_s == network.t_clear_s) == (
            expected["clearing_event_occurrences"]["value"]
        )
        assert fault_acceleration_pu_per_s == pytest.approx(
            expected["fault_initial_acceleration_pu_per_s"]["value"],
            rel=0.0,
            abs=expected["fault_initial_acceleration_pu_per_s"][
                "abs_tolerance_pu_per_s"
            ],
        )
        assert float(result.delta_rad[clear_index]) == pytest.approx(
            expected["delta_rad_at_clearing"]["value"],
            rel=0.0,
            abs=expected["delta_rad_at_clearing"]["abs_tolerance_rad"],
        )
        assert float(result.omega_dev_pu[clear_index]) == pytest.approx(
            expected["omega_dev_pu_at_clearing"]["value"],
            rel=0.0,
            abs=expected["omega_dev_pu_at_clearing"]["abs_tolerance_pu"],
        )
        assert assessment.status.name == expected["first_swing_status"]["value"]
        assert assessment.reason.name == expected["first_swing_reason"]["value"]

        if assessment.status is FirstSwingStatus.STABLE:
            assert assessment.reversal_bracket is not None
            assert assessment.crossing_bracket is None
        else:
            bracket = assessment.crossing_bracket
            assert bracket is not None
            assert assessment.reversal_bracket is None
            assert bracket.left_omega_dev_pu > 0.0
            assert bracket.right_omega_dev_pu > 0.0

        selected_results.append(
            (
                float(result.delta_rad[clear_index]),
                float(result.omega_dev_pu[clear_index]),
                assessment.status,
                assessment.reason,
            )
        )

    assert selected_results[0] == selected_results[1]


def test_adversarial_golden_case_preserves_time_step_sensitivity() -> None:
    golden_case = _load_json(GOLDEN_CASE_PATH)["cases"][
        "adversarial_time_step"
    ]
    input_case = _input_case(golden_case)
    parameters, network, initial_state = _build_inputs(input_case)
    simulation_config = input_case["simulation"]

    for expectation in golden_case["expected_observations"][
        "classifications_by_dt_s"
    ]:
        statuses = []
        for _ in range(2):
            result = simulate_smib_transient(
                parameters,
                initial_state,
                network,
                t_start_s=simulation_config["t_start_s"],
                t_end_s=simulation_config["t_end_s"],
                dt_s=expectation["dt_s"],
            )
            statuses.append(assess_smib_first_swing(result).status.name)

        assert statuses == [expectation["status"], expectation["status"]]


def test_classic_undamped_golden_case_preserves_analytic_cross_check() -> None:
    golden_case = _load_json(GOLDEN_CASE_PATH)["cases"]["classic_undamped"]
    parameters, network, initial_state = _build_inputs(golden_case)
    search_config = {
        key: value
        for key, value in golden_case["cct_search"].items()
        if key != "tolerance_interpretation"
    }
    expected = golden_case["expected_observations"]
    results = []

    expected_evidence_types = {
        "delta_initial_rad": "ANALYTIC_ORACLE",
        "delta_stable_post_rad": "ANALYTIC_ORACLE",
        "delta_unstable_post_rad": "ANALYTIC_ORACLE",
        "delta_critical_rad": "ANALYTIC_ORACLE",
        "stable_t_clear_s": "ACCEPTED_REGRESSION",
        "unstable_t_clear_s": "ACCEPTED_REGRESSION",
        "stable_clearing_angle_rad": "ACCEPTED_REGRESSION",
        "unstable_clearing_angle_rad": "ACCEPTED_REGRESSION",
        "critical_angle_within_temporal_angle_bracket": (
            "CROSS_CHECKED_EVIDENCE"
        ),
    }
    assert {
        metric_name: expectation["evidence_type"]
        for metric_name, expectation in expected.items()
    } == expected_evidence_types

    stable_expected = expected["stable_t_clear_s"]
    unstable_expected = expected["unstable_t_clear_s"]
    assert stable_expected["abs_tolerance_s"] == 1e-12
    assert unstable_expected["abs_tolerance_s"] == 1e-12
    assert stable_expected["abs_tolerance_s"] != search_config[
        "time_tolerance_s"
    ]
    assert (
        stable_expected["value"] + stable_expected["abs_tolerance_s"]
        < unstable_expected["value"] - unstable_expected["abs_tolerance_s"]
    )

    for _ in range(2):
        result = cross_check_smib_critical_clearing(
            parameters,
            initial_state,
            network,
            **search_config,
        )
        analytic = result.critical_angle_result
        temporal = result.clearing_time_result

        for metric_name in (
            "delta_initial_rad",
            "delta_stable_post_rad",
            "delta_unstable_post_rad",
            "delta_critical_rad",
        ):
            assert getattr(analytic, metric_name) == pytest.approx(
                expected[metric_name]["value"],
                rel=0.0,
                abs=expected[metric_name]["abs_tolerance_rad"],
            )

        for metric_name in ("stable_t_clear_s", "unstable_t_clear_s"):
            assert getattr(temporal, metric_name) == pytest.approx(
                expected[metric_name]["value"],
                rel=0.0,
                abs=expected[metric_name]["abs_tolerance_s"],
            )

        for metric_name in (
            "stable_clearing_angle_rad",
            "unstable_clearing_angle_rad",
        ):
            assert getattr(result, metric_name) == pytest.approx(
                expected[metric_name]["value"],
                rel=0.0,
                abs=expected[metric_name]["abs_tolerance_rad"],
            )

        assert parameters.D_pu == 0.0
        assert temporal.stable_t_clear_s < temporal.unstable_t_clear_s
        assert temporal.bracket_width_s <= search_config["time_tolerance_s"]
        assert temporal.stable_evaluation.first_swing.status is (
            FirstSwingStatus.STABLE
        )
        assert temporal.unstable_evaluation.first_swing.status is (
            FirstSwingStatus.UNSTABLE
        )
        assert result.is_consistent is (
            expected["critical_angle_within_temporal_angle_bracket"]["value"]
        )
        results.append(
            (
                analytic.delta_critical_rad,
                temporal.stable_t_clear_s,
                temporal.unstable_t_clear_s,
                result.stable_clearing_angle_rad,
                result.unstable_clearing_angle_rad,
                result.is_consistent,
            )
        )

    assert results[0] == results[1]
