import json
from math import asin, pi
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sincrolab.application import (
    SMIBSimulationResult,
    simulate_smib_transient,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


REFERENCE_CASE_PATHS = {
    "stable": Path(__file__).parents[1]
    / "reference_cases"
    / "stable_transient_smib.json",
    "near_limit": Path(__file__).parents[1]
    / "reference_cases"
    / "near_limit_transient_smib.json",
    "unstable": Path(__file__).parents[1]
    / "reference_cases"
    / "unstable_transient_smib.json",
}


def _load_reference_case(case_name: str) -> dict[str, Any]:
    return json.loads(
        REFERENCE_CASE_PATHS[case_name].read_text(encoding="utf-8")
    )


def _build_case_inputs(
    case_name: str,
) -> tuple[
    dict[str, Any],
    SMIBParameters,
    SMIBTransientNetwork,
    SMIBInitialState,
]:
    case = _load_reference_case(case_name)
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=network.Pmax_prefault_pu,
    )
    initial_state = SMIBInitialState(
        delta_rad=delta0_rad,
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    return case, parameters, network, initial_state


def _simulate_case(
    case_name: str,
) -> tuple[
    dict[str, Any],
    SMIBParameters,
    SMIBTransientNetwork,
    SMIBSimulationResult,
]:
    case, parameters, network, initial_state = _build_case_inputs(case_name)
    simulation = case["simulation"]
    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=simulation["t_start_s"],
        t_end_s=simulation["t_end_s"],
        dt_s=simulation["dt_s"],
    )
    return case, parameters, network, result


def _clearing_index(
    result: SMIBSimulationResult,
    network: SMIBTransientNetwork,
) -> int:
    return int(np.flatnonzero(result.time_s == network.t_clear_s)[0])


def _first_reversal_index(
    result: SMIBSimulationResult,
    clear_index: int,
) -> int | None:
    reversal_offsets = np.flatnonzero(
        (result.omega_dev_pu[clear_index:-1] > 0.0)
        & (result.omega_dev_pu[clear_index + 1 :] <= 0.0)
    )
    if reversal_offsets.size == 0:
        return None
    return clear_index + int(reversal_offsets[0]) + 1


def test_h14_reference_cases_contain_reproducible_synthetic_inputs() -> None:
    expected_case_ids = {
        "near_limit": "near_limit_transient_smib",
        "unstable": "unstable_transient_smib",
    }

    for case_name, expected_case_id in expected_case_ids.items():
        case, parameters, network, initial_state = _build_case_inputs(case_name)

        assert set(case) == {
            "schema_version",
            "case_id",
            "metadata",
            "smib_parameters",
            "transient_network",
            "initial_state",
            "simulation",
        }
        assert case["schema_version"] == 1
        assert case["case_id"] == expected_case_id
        assert case["metadata"]["provenance"] == "synthetic"
        assert case["metadata"]["represents_specific_real_system"] is False
        assert case["metadata"]["purpose"]
        assert case["initial_state"]["delta_rad_source"] == (
            "prefault_equilibrium"
        )
        assert initial_state.delta_rad == pytest.approx(asin(0.7 / 1.2))
        assert initial_state.omega_dev_pu == 0.0


def test_reference_case_family_changes_only_clearing_time() -> None:
    cases = {
        case_name: _load_reference_case(case_name)
        for case_name in REFERENCE_CASE_PATHS
    }
    stable_case = cases["stable"]

    for case in cases.values():
        assert case["smib_parameters"] == stable_case["smib_parameters"]
        assert case["initial_state"] == stable_case["initial_state"]
        assert case["simulation"] == stable_case["simulation"]
        assert {
            key: value
            for key, value in case["transient_network"].items()
            if key != "t_clear_s"
        } == {
            key: value
            for key, value in stable_case["transient_network"].items()
            if key != "t_clear_s"
        }

    assert {
        case_name: case["transient_network"]["t_clear_s"]
        for case_name, case in cases.items()
    } == {
        "stable": 0.20,
        "near_limit": 0.30,
        "unstable": 0.35,
    }


def test_near_limit_case_reverses_with_reduced_first_swing_margin() -> None:
    _, stable_parameters, stable_network, stable_result = _simulate_case(
        "stable"
    )
    _, parameters, network, result = _simulate_case("near_limit")
    clear_index = _clearing_index(result, network)
    stable_clear_index = _clearing_index(stable_result, stable_network)

    assert np.all(np.isfinite(result.time_s))
    assert np.all(np.isfinite(result.delta_rad))
    assert np.all(np.isfinite(result.omega_dev_pu))

    fault_index = int(
        np.flatnonzero(result.time_s == network.t_fault_s)[0]
    )
    fault_boundary_derivative = smib_swing_rhs(
        network.t_fault_s,
        np.array(
            [result.delta_rad[fault_index], result.omega_dev_pu[fault_index]]
        ),
        parameters,
        Pmax_pu=network.Pmax_fault_pu,
    )
    assert fault_boundary_derivative[1] > 0.05
    assert result.omega_dev_pu[clear_index] > (
        stable_result.omega_dev_pu[stable_clear_index]
    )

    postfault_derivative_at_clearing = smib_swing_rhs(
        network.t_clear_s,
        np.array(
            [result.delta_rad[clear_index], result.omega_dev_pu[clear_index]]
        ),
        parameters,
        Pmax_pu=network.Pmax_postfault_pu,
    )
    assert postfault_derivative_at_clearing[1] < -0.04

    reversal_index = _first_reversal_index(result, clear_index)
    stable_reversal_index = _first_reversal_index(
        stable_result,
        stable_clear_index,
    )
    assert reversal_index is not None
    assert stable_reversal_index is not None
    assert result.omega_dev_pu[reversal_index - 1] > 0.0
    assert result.omega_dev_pu[reversal_index] <= 0.0
    assert 0.60 < result.time_s[reversal_index] < 0.70

    first_swing_max_rad = float(
        np.max(result.delta_rad[clear_index : reversal_index + 1])
    )
    stable_first_swing_max_rad = float(
        np.max(
            stable_result.delta_rad[
                stable_clear_index : stable_reversal_index + 1
            ]
        )
    )
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    angular_margin_rad = delta_unstable_post_rad - first_swing_max_rad
    stable_angular_margin_rad = (
        delta_unstable_post_rad - stable_first_swing_max_rad
    )

    assert 2.0 < first_swing_max_rad < 2.3
    assert 0.2 < angular_margin_rad < 0.4
    assert np.all(
        result.delta_rad[clear_index : reversal_index + 1]
        < delta_unstable_post_rad
    )
    assert stable_first_swing_max_rad < first_swing_max_rad
    assert stable_angular_margin_rad > angular_margin_rad
    assert stable_angular_margin_rad - angular_margin_rad > 0.8


def test_unstable_case_crosses_unstable_equilibrium_before_reversal() -> None:
    simulated_cases = {
        case_name: _simulate_case(case_name)
        for case_name in REFERENCE_CASE_PATHS
    }
    clearing_speeds = {}
    for case_name, (_, _, network, result) in simulated_cases.items():
        clearing_speeds[case_name] = result.omega_dev_pu[
            _clearing_index(result, network)
        ]

    assert clearing_speeds["stable"] < clearing_speeds["near_limit"]
    assert clearing_speeds["near_limit"] < clearing_speeds["unstable"]

    _, parameters, network, result = simulated_cases["unstable"]
    clear_index = _clearing_index(result, network)
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    crossing_offsets = np.flatnonzero(
        result.delta_rad[clear_index:] >= delta_unstable_post_rad
    )

    assert np.all(np.isfinite(result.time_s))
    assert np.all(np.isfinite(result.delta_rad))
    assert np.all(np.isfinite(result.omega_dev_pu))
    assert crossing_offsets.size > 0

    crossing_index = clear_index + int(crossing_offsets[0])
    assert result.delta_rad[crossing_index - 1] < delta_unstable_post_rad
    assert result.delta_rad[crossing_index] >= delta_unstable_post_rad
    assert result.omega_dev_pu[crossing_index] > 0.01
    assert np.all(result.omega_dev_pu[clear_index : crossing_index + 1] > 0.0)

    growth_end_index = int(
        np.searchsorted(
            result.time_s,
            result.time_s[crossing_index] + 0.2,
            side="left",
        )
    )
    assert growth_end_index < result.time_s.size
    assert np.all(
        np.diff(result.delta_rad[crossing_index : growth_end_index + 1])
        > 0.0
    )
    assert (
        result.delta_rad[growth_end_index]
        - result.delta_rad[crossing_index]
        > 1.0
    )
    assert np.max(result.delta_rad[crossing_index:]) > 10.0
