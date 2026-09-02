import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sincrolab.analysis import FirstSwingStatus, assess_smib_first_swing
from sincrolab.application import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)

REFERENCE_CASES = Path(__file__).parents[1] / "reference_cases"


def _load_case(filename: str) -> dict[str, Any]:
    return json.loads((REFERENCE_CASES / filename).read_text(encoding="utf-8"))


def _simulate(case: dict[str, Any], *, dt_s: float):
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    simulation = case["simulation"]
    return simulate_smib_transient(
        parameters,
        initial_state,
        network,
        t_start_s=simulation["t_start_s"],
        t_end_s=simulation["t_end_s"],
        dt_s=dt_s,
    )


def _first_swing_margin_rad(result) -> float:
    assessment = assess_smib_first_swing(result)
    bracket = assessment.reversal_bracket
    assert bracket is not None
    first_swing_max_rad = float(
        np.max(result.delta_rad[: bracket.right_index + 1])
    )
    return assessment.delta_unstable_post_rad - first_swing_max_rad


def test_adversarial_case_is_public_synthetic_and_documents_its_limit() -> None:
    case = _load_case("near_critical_adversarial.json")

    assert case["schema_version"] == 1
    assert case["case_id"] == "near_critical_adversarial"
    assert case["metadata"]["provenance"] == "synthetic"
    assert case["metadata"]["represents_specific_real_system"] is False
    assert "time-step sensitivity" in case["metadata"]["limitation"]
    assert "CCT" in case["metadata"]["limitation"]
    assert case["transient_network"]["t_clear_s"] == 0.3045


def test_adversarial_case_is_more_demanding_than_near_limit() -> None:
    adversarial = _simulate(
        _load_case("near_critical_adversarial.json"),
        dt_s=0.005,
    )
    near_limit = _simulate(
        _load_case("near_limit_transient_smib.json"),
        dt_s=0.005,
    )

    adversarial_assessment = assess_smib_first_swing(adversarial)
    near_limit_assessment = assess_smib_first_swing(near_limit)

    assert adversarial_assessment.status is FirstSwingStatus.STABLE
    assert near_limit_assessment.status is FirstSwingStatus.STABLE
    assert 0.0 < _first_swing_margin_rad(adversarial) < 0.2
    assert _first_swing_margin_rad(adversarial) < _first_swing_margin_rad(
        near_limit
    )


@pytest.mark.parametrize("dt_s", [0.005, 0.05, 0.1])
def test_adversarial_sampled_assessment_is_stable_through_dt_0_1(
    dt_s: float,
) -> None:
    result = _simulate(
        _load_case("near_critical_adversarial.json"),
        dt_s=dt_s,
    )

    assert assess_smib_first_swing(result).status is FirstSwingStatus.STABLE


def test_adversarial_coarse_trajectory_exposes_resolution_dependence() -> None:
    result = _simulate(
        _load_case("near_critical_adversarial.json"),
        dt_s=0.2,
    )

    # H15 classifies sampled trajectories; this regression records that the
    # coarse trajectory disagrees, not that dt_s=0.2 establishes physical truth.
    assert assess_smib_first_swing(result).status is FirstSwingStatus.UNSTABLE
