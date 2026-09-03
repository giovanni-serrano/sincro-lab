"""Application use cases for SMIB clearing-time evaluation and CCT search."""

from dataclasses import dataclass, replace
from math import isfinite

from sincrolab.analysis.first_swing import (
    FirstSwingAssessment,
    FirstSwingStatus,
    assess_smib_first_swing,
)
from sincrolab.application.transient import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
)
from sincrolab.simulation import SMIBTransientSimulationResult


@dataclass(frozen=True)
class SMIBClearingTimeEvaluation:
    """Immutable composition of a transient run and its first-swing result."""

    simulation: SMIBTransientSimulationResult
    first_swing: FirstSwingAssessment


@dataclass(frozen=True)
class SMIBCriticalClearingTimeResult:
    """Final stable/unstable time bracket from the SMIB CCT search.

    ``cct_estimate_s`` is only the midpoint of the final bracket. The search
    guarantees a stable lower endpoint, an unstable upper endpoint, and a
    bracket no wider than ``time_tolerance_s`` for the supplied temporal
    configuration; it does not establish convergence with respect to ``dt_s``.
    """

    stable_evaluation: SMIBClearingTimeEvaluation
    unstable_evaluation: SMIBClearingTimeEvaluation
    time_tolerance_s: float
    iterations: int

    @property
    def stable_t_clear_s(self) -> float:
        """Return the final clearing time classified as stable, in seconds."""
        return self.stable_evaluation.simulation.network.t_clear_s

    @property
    def unstable_t_clear_s(self) -> float:
        """Return the final clearing time classified as unstable, in seconds."""
        return self.unstable_evaluation.simulation.network.t_clear_s

    @property
    def bracket_width_s(self) -> float:
        """Return the final stable-to-unstable bracket width, in seconds."""
        return self.unstable_t_clear_s - self.stable_t_clear_s

    @property
    def cct_estimate_s(self) -> float:
        """Return the midpoint of the final bracket, not an exact CCT."""
        return self.stable_t_clear_s + self.bracket_width_s / 2.0


def evaluate_smib_clearing_time(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    network: SMIBTransientNetwork,
    *,
    t_clear_s: float,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBClearingTimeEvaluation:
    """Simulate and assess one clearing time with explicit temporal settings.

    The supplied network is not mutated. Its transfer capabilities and fault
    onset are preserved while ``t_clear_s`` is replaced in a new value object.
    """
    effective_network = replace(network, t_clear_s=t_clear_s)
    if t_end_s <= effective_network.t_clear_s:
        raise ValueError(
            "t_end_s must be greater than t_clear_s for first-swing assessment"
        )

    simulation = simulate_smib_transient(
        parameters,
        initial_state,
        effective_network,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )
    return SMIBClearingTimeEvaluation(
        simulation=simulation,
        first_swing=assess_smib_first_swing(simulation),
    )


def search_smib_critical_clearing_time(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    network: SMIBTransientNetwork,
    *,
    stable_t_clear_s: float,
    unstable_t_clear_s: float,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
    time_tolerance_s: float,
    max_iterations: int = 64,
) -> SMIBCriticalClearingTimeResult:
    """Bisect a validated stable-to-unstable SMIB clearing-time bracket.

    The search assumes that, within the caller-supplied bracket, earlier
    clearing is ``STABLE`` and later clearing is ``UNSTABLE``. Endpoint
    evaluations do not count as iterations; each evaluated midpoint counts as
    one. Any ``INDETERMINATE`` result aborts the search because it cannot select
    a bracket half without inventing a classification.
    """
    _validate_search_inputs(
        stable_t_clear_s=stable_t_clear_s,
        unstable_t_clear_s=unstable_t_clear_s,
        time_tolerance_s=time_tolerance_s,
        max_iterations=max_iterations,
    )

    def evaluate_at(t_clear_s: float) -> SMIBClearingTimeEvaluation:
        return evaluate_smib_clearing_time(
            parameters,
            initial_state,
            network,
            t_clear_s=t_clear_s,
            t_start_s=t_start_s,
            t_end_s=t_end_s,
            dt_s=dt_s,
        )

    stable_evaluation = evaluate_at(stable_t_clear_s)
    _require_endpoint_status(
        stable_evaluation,
        expected_status=FirstSwingStatus.STABLE,
        argument_name="stable_t_clear_s",
    )
    unstable_evaluation = evaluate_at(unstable_t_clear_s)
    _require_endpoint_status(
        unstable_evaluation,
        expected_status=FirstSwingStatus.UNSTABLE,
        argument_name="unstable_t_clear_s",
    )

    iterations = 0
    while (
        unstable_evaluation.simulation.network.t_clear_s
        - stable_evaluation.simulation.network.t_clear_s
        > time_tolerance_s
    ):
        if iterations >= max_iterations:
            bracket_width_s = (
                unstable_evaluation.simulation.network.t_clear_s
                - stable_evaluation.simulation.network.t_clear_s
            )
            raise RuntimeError(
                "critical clearing time search did not reach "
                f"time_tolerance_s={time_tolerance_s!r} within "
                f"max_iterations={max_iterations}; "
                f"bracket_width_s={bracket_width_s!r}"
            )

        stable_time_s = stable_evaluation.simulation.network.t_clear_s
        unstable_time_s = unstable_evaluation.simulation.network.t_clear_s
        midpoint_s = stable_time_s + (unstable_time_s - stable_time_s) / 2.0
        if midpoint_s == stable_time_s or midpoint_s == unstable_time_s:
            raise RuntimeError(
                "critical clearing time bracket cannot be reduced further "
                "with float precision"
            )

        midpoint_evaluation = evaluate_at(midpoint_s)
        iterations += 1
        midpoint_status = midpoint_evaluation.first_swing.status
        if midpoint_status is FirstSwingStatus.STABLE:
            stable_evaluation = midpoint_evaluation
        elif midpoint_status is FirstSwingStatus.UNSTABLE:
            unstable_evaluation = midpoint_evaluation
        else:
            _raise_indeterminate(midpoint_evaluation)

    return SMIBCriticalClearingTimeResult(
        stable_evaluation=stable_evaluation,
        unstable_evaluation=unstable_evaluation,
        time_tolerance_s=time_tolerance_s,
        iterations=iterations,
    )


def _validate_search_inputs(
    *,
    stable_t_clear_s: float,
    unstable_t_clear_s: float,
    time_tolerance_s: float,
    max_iterations: int,
) -> None:
    if not isfinite(stable_t_clear_s) or not isfinite(unstable_t_clear_s):
        raise ValueError("clearing-time bracket endpoints must be finite")
    if stable_t_clear_s >= unstable_t_clear_s:
        raise ValueError(
            "stable_t_clear_s must be less than unstable_t_clear_s"
        )
    if not isfinite(time_tolerance_s) or time_tolerance_s <= 0.0:
        raise ValueError(
            "time_tolerance_s must be finite and greater than zero"
        )
    if (
        isinstance(max_iterations, bool)
        or not isinstance(max_iterations, int)
        or max_iterations <= 0
    ):
        raise ValueError("max_iterations must be an integer greater than zero")


def _require_endpoint_status(
    evaluation: SMIBClearingTimeEvaluation,
    *,
    expected_status: FirstSwingStatus,
    argument_name: str,
) -> None:
    actual_status = evaluation.first_swing.status
    if actual_status is FirstSwingStatus.INDETERMINATE:
        _raise_indeterminate(evaluation)
    if actual_status is not expected_status:
        t_clear_s = evaluation.simulation.network.t_clear_s
        raise ValueError(
            f"{argument_name}={t_clear_s!r} must evaluate as "
            f"{expected_status.name}; got {actual_status.name}"
        )


def _raise_indeterminate(evaluation: SMIBClearingTimeEvaluation) -> None:
    t_clear_s = evaluation.simulation.network.t_clear_s
    reason = evaluation.first_swing.reason
    raise RuntimeError(
        f"clearing-time evaluation at t_clear_s={t_clear_s!r} is "
        f"INDETERMINATE: {reason.name}"
    )
