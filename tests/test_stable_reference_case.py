import json
from dataclasses import replace
from math import asin, pi
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sincrolab.application import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)


REFERENCE_CASE_PATH = (
    Path(__file__).parents[1]
    / "reference_cases"
    / "stable_transient_smib.json"
)


def _load_reference_case() -> dict[str, Any]:
    return json.loads(REFERENCE_CASE_PATH.read_text(encoding="utf-8"))


def _build_case_inputs() -> tuple[
    dict[str, Any],
    SMIBParameters,
    SMIBTransientNetwork,
    SMIBInitialState,
]:
    case = _load_reference_case()
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state_data = case["initial_state"]
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=network.Pmax_prefault_pu,
    )
    initial_state = SMIBInitialState(
        delta_rad=delta0_rad,
        omega_dev_pu=initial_state_data["omega_dev_pu"],
    )
    return case, parameters, network, initial_state


def test_stable_reference_case_contains_reproducible_synthetic_inputs() -> None:
    case, parameters, network, initial_state = _build_case_inputs()

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
    assert case["case_id"] == "stable_transient_smib"
    assert case["metadata"]["provenance"] == "synthetic"
    assert case["metadata"]["represents_specific_real_system"] is False
    assert case["initial_state"]["delta_rad_source"] == (
        "prefault_equilibrium"
    )
    assert parameters.Pmax_pu == network.Pmax_prefault_pu
    assert initial_state.delta_rad == pytest.approx(asin(0.7 / 1.2))
    assert initial_state.omega_dev_pu == 0.0


def test_stable_reference_case_exhibits_a_bounded_first_swing() -> None:
    case, parameters, network, initial_state = _build_case_inputs()
    simulation = case["simulation"]

    result = simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=simulation["t_start_s"],
        t_end_s=simulation["t_end_s"],
        dt_s=simulation["dt_s"],
    )

    assert result.time_s.size == 1001
    assert np.all(np.isfinite(result.time_s))
    assert np.all(np.isfinite(result.delta_rad))
    assert np.all(np.isfinite(result.omega_dev_pu))
    assert np.all(np.diff(result.time_s) > 0.0)
    assert np.count_nonzero(result.time_s == network.t_fault_s) == 1
    assert np.count_nonzero(result.time_s == network.t_clear_s) == 1

    fault_index = int(np.flatnonzero(result.time_s == network.t_fault_s)[0])
    clear_index = int(np.flatnonzero(result.time_s == network.t_clear_s)[0])
    assert np.max(
        np.abs(result.delta_rad[: fault_index + 1] - initial_state.delta_rad)
    ) <= 1e-12
    assert np.max(np.abs(result.omega_dev_pu[: fault_index + 1])) <= 1e-13

    fault_parameters = replace(parameters, Pmax_pu=network.Pmax_fault_pu)
    fault_boundary_derivative = smib_swing_rhs(
        network.t_fault_s,
        np.array(
            [
                result.delta_rad[fault_index],
                result.omega_dev_pu[fault_index],
            ]
        ),
        fault_parameters,
    )
    assert fault_boundary_derivative[1] > 0.05
    assert result.omega_dev_pu[clear_index] > 0.005

    postfault_parameters = replace(
        parameters,
        Pmax_pu=network.Pmax_postfault_pu,
    )
    postfault_accelerations = np.array(
        [
            smib_swing_rhs(
                float(time_s),
                np.array([delta_rad, omega_dev_pu]),
                postfault_parameters,
            )[1]
            for time_s, delta_rad, omega_dev_pu in zip(
                result.time_s[clear_index:],
                result.delta_rad[clear_index:],
                result.omega_dev_pu[clear_index:],
                strict=True,
            )
        ]
    )
    assert np.min(postfault_accelerations) < -0.02

    reversal_offsets = np.flatnonzero(
        (result.omega_dev_pu[clear_index:-1] > 0.0)
        & (result.omega_dev_pu[clear_index + 1 :] <= 0.0)
    )
    assert reversal_offsets.size > 0
    reversal_index = clear_index + int(reversal_offsets[0]) + 1
    assert 0.35 < result.time_s[reversal_index] < 0.55

    delta_max_first_swing = float(
        np.max(result.delta_rad[clear_index : reversal_index + 1])
    )
    delta_stable_post_rad = asin(
        parameters.Pm_pu / network.Pmax_postfault_pu
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    angular_margin_rad = delta_unstable_post_rad - delta_max_first_swing

    assert 1.0 < delta_max_first_swing < 1.4
    assert angular_margin_rad > 1.0
    assert np.max(np.abs(result.delta_rad)) < 1.5
    assert np.max(np.abs(result.omega_dev_pu)) < 0.02
