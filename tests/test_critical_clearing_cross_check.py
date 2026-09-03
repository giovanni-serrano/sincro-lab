import ast
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

import sincrolab.application.critical_clearing_cross_check as cross_check_module
from sincrolab.analysis import (
    CriticalClearingAngleResult,
    FirstSwingStatus,
)
from sincrolab.application import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingCrossCheck,
    SMIBCriticalClearingTimeResult,
    cross_check_smib_critical_clearing,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    initial_equilibrium_angle_rad,
)


REFERENCE_CASE_PATH = (
    Path(__file__).parents[1]
    / "reference_cases"
    / "stable_transient_smib.json"
)


def _case_inputs(
    *,
    D_pu: float = 0.0,
) -> tuple[SMIBParameters, SMIBTransientNetwork, SMIBInitialState]:
    case: dict[str, Any] = json.loads(
        REFERENCE_CASE_PATH.read_text(encoding="utf-8")
    )
    parameters = replace(
        SMIBParameters(**case["smib_parameters"]),
        D_pu=D_pu,
    )
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    return parameters, network, initial_state


def _cross_check(
    *,
    D_pu: float = 0.0,
    angle_tolerance_rad: float = 0.0,
) -> SMIBCriticalClearingCrossCheck:
    parameters, network, initial_state = _case_inputs(D_pu=D_pu)
    return cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.2,
        unstable_t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
        time_tolerance_s=1e-4,
        angle_tolerance_rad=angle_tolerance_rad,
    )


def _critical_angle_result(delta_critical_rad: float) -> CriticalClearingAngleResult:
    return CriticalClearingAngleResult(
        delta_initial_rad=0.5,
        delta_stable_post_rad=0.6,
        delta_unstable_post_rad=2.5,
        critical_cosine_argument=0.25,
        delta_critical_rad=delta_critical_rad,
    )


def _controlled_evaluation(
    *,
    t_clear_s: float,
    delta_clear_rad: float,
    status: FirstSwingStatus,
    time_s: np.ndarray | None = None,
) -> SMIBClearingTimeEvaluation:
    resolved_time_s = (
        np.array([0.0, t_clear_s, 1.0])
        if time_s is None
        else time_s
    )
    delta_rad = np.array([0.5, delta_clear_rad, delta_clear_rad + 0.1])
    return cast(
        SMIBClearingTimeEvaluation,
        SimpleNamespace(
            simulation=SimpleNamespace(
                network=SimpleNamespace(t_clear_s=t_clear_s),
                time_s=resolved_time_s,
                delta_rad=delta_rad,
            ),
            first_swing=SimpleNamespace(status=status),
        ),
    )


def _controlled_time_result(
    *,
    stable_angle_rad: float = 1.0,
    unstable_angle_rad: float = 1.2,
    stable_time_s: np.ndarray | None = None,
) -> SMIBCriticalClearingTimeResult:
    return cast(
        SMIBCriticalClearingTimeResult,
        SimpleNamespace(
            stable_evaluation=_controlled_evaluation(
                t_clear_s=0.25,
                delta_clear_rad=stable_angle_rad,
                status=FirstSwingStatus.STABLE,
                time_s=stable_time_s,
            ),
            unstable_evaluation=_controlled_evaluation(
                t_clear_s=0.5,
                delta_clear_rad=unstable_angle_rad,
                status=FirstSwingStatus.UNSTABLE,
            ),
        ),
    )


def test_integrated_classical_case_cross_checks_independent_predictions() -> None:
    parameters, network, initial_state = _case_inputs()
    network_before = replace(network)

    result = cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.2,
        unstable_t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
        time_tolerance_s=1e-4,
        angle_tolerance_rad=0.0,
    )

    assert result.critical_angle_rad == pytest.approx(
        1.2668967326699028,
        abs=1e-14,
    )
    assert result.clearing_time_result.stable_t_clear_s == pytest.approx(
        0.30524902343749993
    )
    assert result.clearing_time_result.unstable_t_clear_s == pytest.approx(
        0.305322265625
    )
    assert result.stable_clearing_angle_rad == pytest.approx(
        1.2666194202127534,
        abs=1e-12,
    )
    assert result.unstable_clearing_angle_rad == pytest.approx(
        1.2670679820430204,
        abs=1e-12,
    )
    assert result.stable_angle_gap_rad == pytest.approx(
        0.00027731245714934794,
        abs=1e-12,
    )
    assert result.unstable_angle_gap_rad == pytest.approx(
        0.00017124937311763233,
        abs=1e-12,
    )
    assert result.clearing_angle_bracket_width_rad == pytest.approx(
        0.00044856183026698027,
        abs=1e-12,
    )
    assert result.is_consistent is True
    assert result.angle_tolerance_rad == 0.0
    assert (
        result.clearing_time_result.stable_evaluation.first_swing.status
        is FirstSwingStatus.STABLE
    )
    assert (
        result.clearing_time_result.unstable_evaluation.first_swing.status
        is FirstSwingStatus.UNSTABLE
    )
    assert network == network_before


def test_cross_check_preserves_endpoint_provenance_and_existing_owners() -> None:
    parameters, network, initial_state = _case_inputs()

    result = cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.2,
        unstable_t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
        time_tolerance_s=1e-4,
        angle_tolerance_rad=0.0,
    )

    for evaluation in (
        result.clearing_time_result.stable_evaluation,
        result.clearing_time_result.unstable_evaluation,
    ):
        simulation = evaluation.simulation
        assert simulation.parameters is parameters
        assert simulation.initial_state is initial_state
        assert simulation.t_start_s == 0.0
        assert simulation.t_end_s == 5.0
        assert simulation.dt_s == 0.005
        assert simulation.network.Pmax_prefault_pu == 1.2
        assert simulation.network.Pmax_fault_pu == 0.2
        assert simulation.network.Pmax_postfault_pu == 1.1
        assert simulation.network.t_fault_s == 0.1

    assert {field.name for field in fields(result)} == {
        "critical_angle_result",
        "clearing_time_result",
        "angle_tolerance_rad",
    }


def test_h17_result_cannot_change_the_caller_bracket_sent_to_h19(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters, network, initial_state = _case_inputs()
    call_order: list[str] = []
    search_calls: list[dict[str, object]] = []
    critical_angle_rad = 1.05
    time_result = _controlled_time_result()

    def compute_controlled(*args: object, **kwargs: object):
        call_order.append("H17")
        return _critical_angle_result(critical_angle_rad)

    def search_controlled(*args: object, **kwargs: object):
        call_order.append("H19")
        search_calls.append(dict(kwargs))
        assert args == (parameters, initial_state, network)
        return time_result

    monkeypatch.setattr(
        cross_check_module,
        "compute_critical_clearing_angle",
        compute_controlled,
    )
    monkeypatch.setattr(
        cross_check_module,
        "search_smib_critical_clearing_time",
        search_controlled,
    )

    first = cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.21,
        unstable_t_clear_s=0.34,
        t_start_s=0.01,
        t_end_s=4.0,
        dt_s=0.007,
        time_tolerance_s=2e-4,
        angle_tolerance_rad=0.1,
        max_iterations=31,
    )
    critical_angle_rad = 99.0
    second = cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.21,
        unstable_t_clear_s=0.34,
        t_start_s=0.01,
        t_end_s=4.0,
        dt_s=0.007,
        time_tolerance_s=2e-4,
        angle_tolerance_rad=0.1,
        max_iterations=31,
    )

    assert first.critical_angle_rad == 1.05
    assert second.critical_angle_rad == 99.0
    assert call_order == ["H17", "H19", "H17", "H19"]
    assert search_calls == [search_calls[0], search_calls[0]]
    assert search_calls[0] == {
        "stable_t_clear_s": 0.21,
        "unstable_t_clear_s": 0.34,
        "t_start_s": 0.01,
        "t_end_s": 4.0,
        "dt_s": 0.007,
        "time_tolerance_s": 2e-4,
        "max_iterations": 31,
    }
    assert first.clearing_time_result is time_result
    assert second.clearing_time_result is time_result


def test_clearing_angles_come_from_h19_endpoint_trajectories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters, network, initial_state = _case_inputs()
    critical_result = _critical_angle_result(1.1)
    time_result = _controlled_time_result(
        stable_angle_rad=1.0,
        unstable_angle_rad=1.2,
    )
    monkeypatch.setattr(
        cross_check_module,
        "compute_critical_clearing_angle",
        lambda *args, **kwargs: critical_result,
    )
    monkeypatch.setattr(
        cross_check_module,
        "search_smib_critical_clearing_time",
        lambda *args, **kwargs: time_result,
    )

    result = cross_check_smib_critical_clearing(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=0.2,
        unstable_t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
        time_tolerance_s=1e-4,
        angle_tolerance_rad=0.0,
    )

    assert result.critical_angle_result is critical_result
    assert result.clearing_time_result is time_result
    assert result.stable_clearing_angle_rad == 1.0
    assert result.unstable_clearing_angle_rad == 1.2
    assert result.stable_angle_gap_rad == pytest.approx(0.1)
    assert result.unstable_angle_gap_rad == pytest.approx(0.1)


def test_missing_exact_clearing_sample_is_rejected_without_nearest_lookup() -> None:
    time_result = _controlled_time_result(
        stable_time_s=np.array([0.0, 0.249, 0.251]),
    )

    with pytest.raises(ValueError, match="contain t_clear_s exactly once"):
        SMIBCriticalClearingCrossCheck(
            critical_angle_result=_critical_angle_result(1.1),
            clearing_time_result=time_result,
            angle_tolerance_rad=0.0,
        )


def test_cross_check_result_is_immutable() -> None:
    result = _cross_check()

    with pytest.raises(FrozenInstanceError):
        result.angle_tolerance_rad = 1.0  # type: ignore[misc]


def test_angular_tolerance_has_inclusive_boundary_semantics() -> None:
    time_result = _controlled_time_result(
        stable_angle_rad=1.25,
        unstable_angle_rad=1.5,
    )
    at_boundary = SMIBCriticalClearingCrossCheck(
        critical_angle_result=_critical_angle_result(1.0),
        clearing_time_result=time_result,
        angle_tolerance_rad=0.25,
    )
    outside_tolerance = SMIBCriticalClearingCrossCheck(
        critical_angle_result=_critical_angle_result(1.0),
        clearing_time_result=time_result,
        angle_tolerance_rad=0.125,
    )

    assert at_boundary.stable_angle_gap_rad == -0.25
    assert at_boundary.unstable_angle_gap_rad == 0.5
    assert at_boundary.is_consistent is True
    assert outside_tolerance.is_consistent is False


@pytest.mark.parametrize(
    "invalid_angle_tolerance_rad",
    [-0.1, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_angular_tolerance_is_rejected_before_either_path(
    invalid_angle_tolerance_rad: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters, network, initial_state = _case_inputs()
    calls: list[str] = []
    monkeypatch.setattr(
        cross_check_module,
        "compute_critical_clearing_angle",
        lambda *args, **kwargs: calls.append("H17"),
    )
    monkeypatch.setattr(
        cross_check_module,
        "search_smib_critical_clearing_time",
        lambda *args, **kwargs: calls.append("H19"),
    )

    with pytest.raises(ValueError, match="angle_tolerance_rad"):
        cross_check_smib_critical_clearing(
            parameters,
            initial_state,
            network,
            stable_t_clear_s=0.2,
            unstable_t_clear_s=0.35,
            t_start_s=0.0,
            t_end_s=5.0,
            dt_s=0.005,
            time_tolerance_s=1e-4,
            angle_tolerance_rad=invalid_angle_tolerance_rad,
        )

    assert calls == []


def test_h17_domain_error_propagates_without_running_h19(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters, network, initial_state = _case_inputs(D_pu=0.2)
    h19_calls = 0

    def unexpected_h19(*args: object, **kwargs: object):
        nonlocal h19_calls
        h19_calls += 1
        raise AssertionError("H19 must not run after an H17 domain error")

    monkeypatch.setattr(
        cross_check_module,
        "search_smib_critical_clearing_time",
        unexpected_h19,
    )

    with pytest.raises(ValueError, match=r"requires D_pu == 0"):
        cross_check_smib_critical_clearing(
            parameters,
            initial_state,
            network,
            stable_t_clear_s=0.2,
            unstable_t_clear_s=0.35,
            t_start_s=0.0,
            t_end_s=5.0,
            dt_s=0.005,
            time_tolerance_s=1e-4,
            angle_tolerance_rad=0.0,
        )

    assert h19_calls == 0


def test_h19_indeterminate_error_propagates_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameters, network, initial_state = _case_inputs()
    h19_calls = 0
    monkeypatch.setattr(
        cross_check_module,
        "compute_critical_clearing_angle",
        lambda *args, **kwargs: _critical_angle_result(1.1),
    )

    def indeterminate_h19(*args: object, **kwargs: object):
        nonlocal h19_calls
        h19_calls += 1
        raise RuntimeError(
            "clearing-time evaluation at t_clear_s=0.3 is "
            "INDETERMINATE: HORIZON_ENDED_BEFORE_EVENT"
        )

    monkeypatch.setattr(
        cross_check_module,
        "search_smib_critical_clearing_time",
        indeterminate_h19,
    )

    with pytest.raises(
        RuntimeError,
        match=r"t_clear_s=0\.3.*INDETERMINATE.*HORIZON_ENDED",
    ):
        cross_check_smib_critical_clearing(
            parameters,
            initial_state,
            network,
            stable_t_clear_s=0.2,
            unstable_t_clear_s=0.35,
            t_start_s=0.0,
            t_end_s=5.0,
            dt_s=0.005,
            time_tolerance_s=1e-4,
            angle_tolerance_rad=0.0,
        )

    assert h19_calls == 1


def test_cross_check_imports_preserve_architectural_direction() -> None:
    tree = ast.parse(inspect.getsource(cross_check_module))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "sincrolab.application.clearing_time"
        for alias in node.names
    }

    assert imported_names == {
        "SMIBClearingTimeEvaluation",
        "SMIBCriticalClearingTimeResult",
        "search_smib_critical_clearing_time",
    }
    assert not hasattr(cross_check_module, "evaluate_smib_clearing_time")
    assert not hasattr(cross_check_module, "simulate_smib_transient")
    assert not hasattr(cross_check_module, "assess_smib_first_swing")
