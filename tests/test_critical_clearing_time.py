import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

import sincrolab.application.clearing_time as clearing_time_module
from sincrolab.analysis import FirstSwingReason, FirstSwingStatus
from sincrolab.application import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
    search_smib_critical_clearing_time,
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


def _case_inputs() -> tuple[
    dict[str, Any],
    SMIBParameters,
    SMIBTransientNetwork,
    SMIBInitialState,
]:
    case = json.loads(REFERENCE_CASE_PATH.read_text(encoding="utf-8"))
    parameters = SMIBParameters(**case["smib_parameters"])
    network = SMIBTransientNetwork(**case["transient_network"])
    initial_state = SMIBInitialState(
        delta_rad=initial_equilibrium_angle_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_prefault_pu=network.Pmax_prefault_pu,
        ),
        omega_dev_pu=case["initial_state"]["omega_dev_pu"],
    )
    return case, parameters, network, initial_state


def _search(
    *,
    stable_t_clear_s: float = 0.2,
    unstable_t_clear_s: float = 0.35,
    t_start_s: float = 0.0,
    t_end_s: float = 5.0,
    dt_s: float = 0.005,
    time_tolerance_s: float = 1e-4,
    max_iterations: int = 64,
) -> SMIBCriticalClearingTimeResult:
    _, parameters, network, initial_state = _case_inputs()
    return search_smib_critical_clearing_time(
        parameters,
        initial_state,
        network,
        stable_t_clear_s=stable_t_clear_s,
        unstable_t_clear_s=unstable_t_clear_s,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
        time_tolerance_s=time_tolerance_s,
        max_iterations=max_iterations,
    )


def _controlled_evaluation(
    t_clear_s: float,
    *,
    status: FirstSwingStatus,
    reason: FirstSwingReason,
) -> SMIBClearingTimeEvaluation:
    return cast(
        SMIBClearingTimeEvaluation,
        SimpleNamespace(
            simulation=SimpleNamespace(
                network=SimpleNamespace(t_clear_s=t_clear_s)
            ),
            first_swing=SimpleNamespace(status=status, reason=reason),
        ),
    )


def test_search_converges_to_a_traceable_stable_unstable_bracket() -> None:
    result = _search()

    assert isinstance(result, SMIBCriticalClearingTimeResult)
    assert result.stable_evaluation.first_swing.status is FirstSwingStatus.STABLE
    assert (
        result.unstable_evaluation.first_swing.status
        is FirstSwingStatus.UNSTABLE
    )
    assert 0.2 <= result.stable_t_clear_s < result.unstable_t_clear_s <= 0.35
    assert result.bracket_width_s <= result.time_tolerance_s
    assert result.time_tolerance_s == 1e-4
    assert result.cct_estimate_s == (
        result.stable_t_clear_s + result.unstable_t_clear_s
    ) / 2.0
    assert result.iterations == 11
    assert {field.name for field in fields(result)} == {
        "stable_evaluation",
        "unstable_evaluation",
        "time_tolerance_s",
        "iterations",
    }


def test_one_midpoint_evaluation_counts_as_one_iteration() -> None:
    result = _search(time_tolerance_s=0.08)

    assert result.iterations == 1
    assert result.stable_t_clear_s == pytest.approx(0.275)
    assert result.unstable_t_clear_s == 0.35
    assert result.bracket_width_s == pytest.approx(0.075)


def test_exact_tolerance_width_evaluates_endpoints_without_midpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_times_s: list[float] = []

    def evaluate_controlled(*args: object, **kwargs: object):
        t_clear_s = float(kwargs["t_clear_s"])
        evaluated_times_s.append(t_clear_s)
        if t_clear_s == 0.25:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.STABLE,
                reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            )
        if t_clear_s == 0.5:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.UNSTABLE,
                reason=FirstSwingReason.CROSSING_BEFORE_REVERSAL,
            )
        raise AssertionError(f"unexpected midpoint evaluation at {t_clear_s}")

    monkeypatch.setattr(
        clearing_time_module,
        "evaluate_smib_clearing_time",
        evaluate_controlled,
    )

    result = _search(
        stable_t_clear_s=0.25,
        unstable_t_clear_s=0.5,
        time_tolerance_s=0.25,
    )

    assert result.iterations == 0
    assert result.stable_t_clear_s == 0.25
    assert result.unstable_t_clear_s == 0.5
    assert result.bracket_width_s == result.time_tolerance_s == 0.25
    assert evaluated_times_s == [0.25, 0.5]


def test_search_reuses_h18_for_endpoints_and_each_midpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_times_s: list[float] = []
    original_evaluate = clearing_time_module.evaluate_smib_clearing_time

    def evaluate_spy(*args: object, **kwargs: object):
        evaluated_times_s.append(float(kwargs["t_clear_s"]))
        return original_evaluate(*args, **kwargs)

    monkeypatch.setattr(
        clearing_time_module,
        "evaluate_smib_clearing_time",
        evaluate_spy,
    )

    result = _search(time_tolerance_s=0.08)

    assert result.iterations == 1
    assert evaluated_times_s == pytest.approx([0.2, 0.35, 0.275])


def test_search_is_deterministic() -> None:
    first = _search(time_tolerance_s=1e-3)
    second = _search(time_tolerance_s=1e-3)

    assert first.stable_t_clear_s == second.stable_t_clear_s
    assert first.unstable_t_clear_s == second.unstable_t_clear_s
    assert first.cct_estimate_s == second.cct_estimate_s
    assert first.bracket_width_s == second.bracket_width_s
    assert first.iterations == second.iterations
    assert first.stable_evaluation.first_swing == (
        second.stable_evaluation.first_swing
    )
    assert first.unstable_evaluation.first_swing == (
        second.unstable_evaluation.first_swing
    )
    np.testing.assert_array_equal(
        first.stable_evaluation.simulation.delta_rad,
        second.stable_evaluation.simulation.delta_rad,
    )
    np.testing.assert_array_equal(
        first.unstable_evaluation.simulation.delta_rad,
        second.unstable_evaluation.simulation.delta_rad,
    )


def test_result_is_immutable() -> None:
    result = _search(time_tolerance_s=0.08)

    with pytest.raises(FrozenInstanceError):
        result.iterations = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    ("stable_t_clear_s", "unstable_t_clear_s"),
    [(0.2, 0.2), (0.3, 0.2)],
    ids=["equal", "reversed"],
)
def test_search_rejects_unordered_initial_bracket(
    stable_t_clear_s: float,
    unstable_t_clear_s: float,
) -> None:
    with pytest.raises(ValueError, match="must be less than"):
        _search(
            stable_t_clear_s=stable_t_clear_s,
            unstable_t_clear_s=unstable_t_clear_s,
        )


@pytest.mark.parametrize(
    ("stable_t_clear_s", "unstable_t_clear_s", "message"),
    [
        (0.35, 0.36, "stable_t_clear_s.*STABLE.*UNSTABLE"),
        (0.2, 0.3, "unstable_t_clear_s.*UNSTABLE.*STABLE"),
    ],
    ids=["lower_not_stable", "upper_not_unstable"],
)
def test_search_validates_actual_endpoint_classifications(
    stable_t_clear_s: float,
    unstable_t_clear_s: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _search(
            stable_t_clear_s=stable_t_clear_s,
            unstable_t_clear_s=unstable_t_clear_s,
        )


@pytest.mark.parametrize(
    ("stable_t_clear_s", "unstable_t_clear_s"),
    [
        (float("nan"), 0.35),
        (0.2, float("inf")),
        (float("-inf"), 0.35),
    ],
)
def test_search_rejects_nonfinite_bracket_endpoints(
    stable_t_clear_s: float,
    unstable_t_clear_s: float,
) -> None:
    with pytest.raises(ValueError, match="endpoints must be finite"):
        _search(
            stable_t_clear_s=stable_t_clear_s,
            unstable_t_clear_s=unstable_t_clear_s,
        )


@pytest.mark.parametrize(
    "invalid_time_tolerance_s",
    [0.0, -1e-3, float("nan"), float("inf"), float("-inf")],
)
def test_search_rejects_invalid_time_tolerance(
    invalid_time_tolerance_s: float,
) -> None:
    with pytest.raises(ValueError, match="time_tolerance_s"):
        _search(time_tolerance_s=invalid_time_tolerance_s)


@pytest.mark.parametrize("invalid_max_iterations", [0, -1, 1.0, True])
def test_search_rejects_invalid_max_iterations(
    invalid_max_iterations: object,
) -> None:
    with pytest.raises(ValueError, match="max_iterations"):
        _search(max_iterations=invalid_max_iterations)  # type: ignore[arg-type]


def test_search_does_not_report_success_when_max_iterations_is_exhausted() -> None:
    with pytest.raises(
        RuntimeError,
        match=r"max_iterations=1; bracket_width_s=0\.074999",
    ):
        _search(time_tolerance_s=1e-6, max_iterations=1)


def test_indeterminate_endpoint_stops_search_with_time_status_and_reason() -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            r"t_clear_s=0\.2.*INDETERMINATE: "
            r"HORIZON_ENDED_BEFORE_EVENT"
        ),
    ):
        _search(t_end_s=0.3)


def test_indeterminate_upper_endpoint_stops_before_any_midpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_times_s: list[float] = []

    def evaluate_controlled(*args: object, **kwargs: object):
        t_clear_s = float(kwargs["t_clear_s"])
        evaluated_times_s.append(t_clear_s)
        if t_clear_s == 0.25:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.STABLE,
                reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            )
        if t_clear_s == 0.5:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.INDETERMINATE,
                reason=FirstSwingReason.EVENT_ORDER_AMBIGUOUS,
            )
        raise AssertionError(f"search continued after {t_clear_s}")

    monkeypatch.setattr(
        clearing_time_module,
        "evaluate_smib_clearing_time",
        evaluate_controlled,
    )

    with pytest.raises(
        RuntimeError,
        match=r"t_clear_s=0\.5.*INDETERMINATE: EVENT_ORDER_AMBIGUOUS",
    ):
        _search(
            stable_t_clear_s=0.25,
            unstable_t_clear_s=0.5,
            time_tolerance_s=0.125,
        )

    assert evaluated_times_s == [0.25, 0.5]


def test_indeterminate_midpoint_stops_without_further_evaluations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluated_times_s: list[float] = []

    def evaluate_controlled(*args: object, **kwargs: object):
        t_clear_s = float(kwargs["t_clear_s"])
        evaluated_times_s.append(t_clear_s)
        if t_clear_s == 0.25:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.STABLE,
                reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
            )
        if t_clear_s == 0.5:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.UNSTABLE,
                reason=FirstSwingReason.CROSSING_BEFORE_REVERSAL,
            )
        if t_clear_s == 0.375:
            return _controlled_evaluation(
                t_clear_s,
                status=FirstSwingStatus.INDETERMINATE,
                reason=FirstSwingReason.NO_POSITIVE_EXCURSION,
            )
        raise AssertionError(f"search continued after {t_clear_s}")

    monkeypatch.setattr(
        clearing_time_module,
        "evaluate_smib_clearing_time",
        evaluate_controlled,
    )

    with pytest.raises(
        RuntimeError,
        match=r"t_clear_s=0\.375.*INDETERMINATE: NO_POSITIVE_EXCURSION",
    ):
        _search(
            stable_t_clear_s=0.25,
            unstable_t_clear_s=0.5,
            time_tolerance_s=0.125,
        )

    assert evaluated_times_s == [0.25, 0.5, 0.375]


def test_final_endpoint_evaluations_preserve_provenance_without_mutation() -> None:
    _, parameters, base_network, initial_state = _case_inputs()
    base_network_before = replace(base_network)

    result = search_smib_critical_clearing_time(
        parameters,
        initial_state,
        base_network,
        stable_t_clear_s=0.2,
        unstable_t_clear_s=0.35,
        t_start_s=0.0,
        t_end_s=5.0,
        dt_s=0.005,
        time_tolerance_s=1e-3,
    )

    stable_simulation = result.stable_evaluation.simulation
    unstable_simulation = result.unstable_evaluation.simulation
    for simulation in (stable_simulation, unstable_simulation):
        assert simulation.parameters is parameters
        assert simulation.initial_state is initial_state
        assert simulation.t_start_s == 0.0
        assert simulation.t_end_s == 5.0
        assert simulation.dt_s == 0.005
        assert simulation.network.Pmax_prefault_pu == 1.2
        assert simulation.network.Pmax_fault_pu == 0.2
        assert simulation.network.Pmax_postfault_pu == 1.1
        assert simulation.network.t_fault_s == 0.1

    stable_network = stable_simulation.network
    unstable_network = unstable_simulation.network
    assert stable_network.t_clear_s == result.stable_t_clear_s
    assert unstable_network.t_clear_s == result.unstable_t_clear_s
    assert {
        key: value
        for key, value in stable_network.__dict__.items()
        if key != "t_clear_s"
    } == {
        key: value
        for key, value in unstable_network.__dict__.items()
        if key != "t_clear_s"
    }
    assert base_network == base_network_before
    assert base_network.t_clear_s == 0.2


def test_search_logic_is_independent_from_direct_pipeline_and_equal_area() -> None:
    source = inspect.getsource(
        clearing_time_module.search_smib_critical_clearing_time
    )

    assert "evaluate_smib_clearing_time" in source
    assert "simulate_smib_transient" not in source
    assert "assess_smib_first_swing" not in source
    assert "assess_equal_area" not in source
    assert "compute_critical_clearing_angle" not in source
