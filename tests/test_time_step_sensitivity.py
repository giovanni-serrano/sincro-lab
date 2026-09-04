import json
from dataclasses import dataclass, replace
from math import ceil, isfinite, log2
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sincrolab.analysis import FirstSwingStatus, assess_smib_first_swing
from sincrolab.application import (
    SMIBCriticalClearingTimeResult,
    search_smib_critical_clearing_time,
    simulate_smib_transient,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)


REFERENCE_CASES = Path(__file__).parents[1] / "reference_cases"
DT_S_VALUES = (0.2, 0.1, 0.05, 0.025)
STABLE_T_CLEAR_S = 0.2
UNSTABLE_T_CLEAR_S = 0.35
T_START_S = 0.0
T_END_S = 5.0
TIME_TOLERANCE_S = 1e-4
MAX_ITERATIONS = 64


@dataclass(frozen=True)
class CCTRefinementShift:
    coarse_dt_s: float
    fine_dt_s: float
    stable_endpoint_shift_s: float
    unstable_endpoint_shift_s: float
    cct_estimate_shift_s: float


def _load_case(filename: str) -> dict[str, Any]:
    return json.loads((REFERENCE_CASES / filename).read_text(encoding="utf-8"))


def _case_inputs(
    filename: str,
) -> tuple[SMIBParameters, SMIBTransientNetwork, SMIBInitialState]:
    case = _load_case(filename)
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


def _search_cct(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
    initial_state: SMIBInitialState,
    *,
    dt_s: float,
) -> SMIBCriticalClearingTimeResult:
    return search_smib_critical_clearing_time(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=STABLE_T_CLEAR_S,
        unstable_t_clear_s=UNSTABLE_T_CLEAR_S,
        t_start_s=T_START_S,
        t_end_s=T_END_S,
        dt_s=dt_s,
        time_tolerance_s=TIME_TOLERANCE_S,
        max_iterations=MAX_ITERATIONS,
    )


def _successive_cct_shifts(
    results: dict[float, SMIBCriticalClearingTimeResult],
) -> list[CCTRefinementShift]:
    shifts = []
    for coarse_dt_s, fine_dt_s in zip(DT_S_VALUES, DT_S_VALUES[1:]):
        coarse = results[coarse_dt_s]
        fine = results[fine_dt_s]
        shifts.append(
            CCTRefinementShift(
                coarse_dt_s=coarse_dt_s,
                fine_dt_s=fine_dt_s,
                stable_endpoint_shift_s=abs(
                    fine.stable_t_clear_s - coarse.stable_t_clear_s
                ),
                unstable_endpoint_shift_s=abs(
                    fine.unstable_t_clear_s - coarse.unstable_t_clear_s
                ),
                cct_estimate_shift_s=abs(
                    fine.cct_estimate_s - coarse.cct_estimate_s
                ),
            )
        )
    return shifts


@pytest.fixture(scope="module")
def controlled_case_inputs(
) -> tuple[SMIBParameters, SMIBTransientNetwork, SMIBInitialState]:
    return _case_inputs("stable_transient_smib.json")


@pytest.fixture(scope="module")
def cct_study_results(
    controlled_case_inputs: tuple[
        SMIBParameters,
        SMIBTransientNetwork,
        SMIBInitialState,
    ],
) -> dict[float, SMIBCriticalClearingTimeResult]:
    parameters, network, initial_state = controlled_case_inputs
    return {
        dt_s: _search_cct(parameters, network, initial_state, dt_s=dt_s)
        for dt_s in DT_S_VALUES
    }


def test_cct_study_changes_only_dt_and_preserves_h19_contract(
    controlled_case_inputs: tuple[
        SMIBParameters,
        SMIBTransientNetwork,
        SMIBInitialState,
    ],
    cct_study_results: dict[float, SMIBCriticalClearingTimeResult],
) -> None:
    parameters, network, initial_state = controlled_case_inputs
    expected_iterations = ceil(
        log2(
            (UNSTABLE_T_CLEAR_S - STABLE_T_CLEAR_S) / TIME_TOLERANCE_S
        )
    )

    for dt_s, result in cct_study_results.items():
        assert result.time_tolerance_s == TIME_TOLERANCE_S
        assert result.iterations == expected_iterations
        assert result.iterations <= MAX_ITERATIONS
        assert (
            STABLE_T_CLEAR_S
            <= result.stable_t_clear_s
            < result.unstable_t_clear_s
            <= UNSTABLE_T_CLEAR_S
        )
        assert result.bracket_width_s <= TIME_TOLERANCE_S
        assert result.cct_estimate_s == (
            result.stable_t_clear_s + result.unstable_t_clear_s
        ) / 2.0
        assert (
            result.stable_evaluation.first_swing.status
            is FirstSwingStatus.STABLE
        )
        assert (
            result.unstable_evaluation.first_swing.status
            is FirstSwingStatus.UNSTABLE
        )

        for evaluation in (
            result.stable_evaluation,
            result.unstable_evaluation,
        ):
            simulation = evaluation.simulation
            assert simulation.parameters is parameters
            assert simulation.initial_state is initial_state
            assert simulation.network == replace(
                network,
                t_clear_s=simulation.network.t_clear_s,
            )
            assert simulation.t_start_s == T_START_S
            assert simulation.t_end_s == T_END_S
            assert simulation.dt_s == dt_s


def test_fixed_time_tolerance_does_not_imply_dt_converged_cct_brackets(
    cct_study_results: dict[float, SMIBCriticalClearingTimeResult],
) -> None:
    shifts = _successive_cct_shifts(cct_study_results)
    coarse_shift, intermediate_shift, fine_shift = shifts

    assert coarse_shift.cct_estimate_shift_s > TIME_TOLERANCE_S
    assert (
        intermediate_shift.stable_endpoint_shift_s
        < coarse_shift.stable_endpoint_shift_s
    )
    assert (
        intermediate_shift.unstable_endpoint_shift_s
        < coarse_shift.unstable_endpoint_shift_s
    )
    assert (
        intermediate_shift.cct_estimate_shift_s
        < coarse_shift.cct_estimate_shift_s
    )
    assert (
        fine_shift.stable_endpoint_shift_s
        <= intermediate_shift.stable_endpoint_shift_s
    )
    assert (
        fine_shift.unstable_endpoint_shift_s
        <= intermediate_shift.unstable_endpoint_shift_s
    )
    assert (
        fine_shift.cct_estimate_shift_s
        <= intermediate_shift.cct_estimate_shift_s
    )


def test_fixed_physical_trajectory_stabilizes_at_common_final_time(
    controlled_case_inputs: tuple[
        SMIBParameters,
        SMIBTransientNetwork,
        SMIBInitialState,
    ],
) -> None:
    parameters, network, initial_state = controlled_case_inputs
    final_states = []

    for dt_s in DT_S_VALUES:
        result = simulate_smib_transient(
            parameters,
            initial_state,
            network,
            t_start_s=T_START_S,
            t_end_s=T_END_S,
            dt_s=dt_s,
        )
        assert result.time_s[-1] == T_END_S
        assert np.count_nonzero(result.time_s == network.t_fault_s) == 1
        assert np.count_nonzero(result.time_s == network.t_clear_s) == 1
        assert assess_smib_first_swing(result).status is FirstSwingStatus.STABLE
        assert np.all(np.isfinite(result.delta_rad))
        assert np.all(np.isfinite(result.omega_dev_pu))
        final_states.append(
            np.array(
                [result.delta_rad[-1], result.omega_dev_pu[-1]],
                dtype=np.float64,
            )
        )

    successive_shifts = [
        np.abs(fine - coarse)
        for coarse, fine in zip(final_states, final_states[1:])
    ]
    for coarse_shift, fine_shift in zip(
        successive_shifts,
        successive_shifts[1:],
    ):
        assert np.all(fine_shift < coarse_shift)


def test_adversarial_first_swing_preserves_resolution_sensitivity() -> None:
    parameters, network, initial_state = _case_inputs(
        "near_critical_adversarial.json"
    )
    statuses = {}

    for dt_s in DT_S_VALUES:
        result = simulate_smib_transient(
            parameters,
            initial_state,
            network,
            t_start_s=T_START_S,
            t_end_s=T_END_S,
            dt_s=dt_s,
        )
        statuses[dt_s] = assess_smib_first_swing(result).status

    assert statuses == {
        0.2: FirstSwingStatus.UNSTABLE,
        0.1: FirstSwingStatus.STABLE,
        0.05: FirstSwingStatus.STABLE,
        0.025: FirstSwingStatus.STABLE,
    }
    assert FirstSwingStatus.INDETERMINATE not in statuses.values()


def test_cct_sensitivity_results_are_deterministic_and_finite(
    controlled_case_inputs: tuple[
        SMIBParameters,
        SMIBTransientNetwork,
        SMIBInitialState,
    ],
    cct_study_results: dict[float, SMIBCriticalClearingTimeResult],
) -> None:
    parameters, network, initial_state = controlled_case_inputs

    for dt_s, first in cct_study_results.items():
        second = _search_cct(parameters, network, initial_state, dt_s=dt_s)
        first_metrics = (
            first.stable_t_clear_s,
            first.unstable_t_clear_s,
            first.bracket_width_s,
            first.cct_estimate_s,
            float(first.iterations),
        )
        second_metrics = (
            second.stable_t_clear_s,
            second.unstable_t_clear_s,
            second.bracket_width_s,
            second.cct_estimate_s,
            float(second.iterations),
        )

        assert all(isfinite(value) for value in first_metrics)
        assert first_metrics == second_metrics
