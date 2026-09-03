"""Application cross-check between analytic and temporal SMIB limits."""

from dataclasses import dataclass
from math import isfinite

from sincrolab.analysis.equal_area import (
    CriticalClearingAngleResult,
    compute_critical_clearing_angle,
)
from sincrolab.application.clearing_time import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
    search_smib_critical_clearing_time,
)
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
)


@dataclass(frozen=True)
class SMIBCriticalClearingCrossCheck:
    """Immutable comparison of independent analytic and temporal results.

    ``angle_tolerance_rad`` is only an angular comparison allowance. It is not
    an RK4 error estimate, a time tolerance, an equal-area tolerance, or a
    claim of physical uncertainty.
    """

    critical_angle_result: CriticalClearingAngleResult
    clearing_time_result: SMIBCriticalClearingTimeResult
    angle_tolerance_rad: float

    def __post_init__(self) -> None:
        _validate_angle_tolerance(self.angle_tolerance_rad)
        _clearing_angle_rad(self.clearing_time_result.stable_evaluation)
        _clearing_angle_rad(self.clearing_time_result.unstable_evaluation)

    @property
    def critical_angle_rad(self) -> float:
        return self.critical_angle_result.delta_critical_rad

    @property
    def stable_clearing_angle_rad(self) -> float:
        return _clearing_angle_rad(
            self.clearing_time_result.stable_evaluation
        )

    @property
    def unstable_clearing_angle_rad(self) -> float:
        return _clearing_angle_rad(
            self.clearing_time_result.unstable_evaluation
        )

    @property
    def stable_angle_gap_rad(self) -> float:
        """Return analytic angle minus the stable-endpoint clearing angle."""
        return self.critical_angle_rad - self.stable_clearing_angle_rad

    @property
    def unstable_angle_gap_rad(self) -> float:
        """Return unstable-endpoint clearing angle minus the analytic angle."""
        return self.unstable_clearing_angle_rad - self.critical_angle_rad

    @property
    def clearing_angle_bracket_width_rad(self) -> float:
        return (
            self.unstable_clearing_angle_rad
            - self.stable_clearing_angle_rad
        )

    @property
    def is_consistent(self) -> bool:
        """Return whether the analytic angle lies within the allowed bracket."""
        return (
            self.stable_angle_gap_rad >= -self.angle_tolerance_rad
            and self.unstable_angle_gap_rad >= -self.angle_tolerance_rad
        )


def cross_check_smib_critical_clearing(
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
    angle_tolerance_rad: float,
    max_iterations: int = 64,
) -> SMIBCriticalClearingCrossCheck:
    """Compare H17's angle with H19's final endpoint trajectories.

    The analytic result is computed first from physical inputs alone. The
    temporal search then receives the caller's bracket unchanged. Only after
    both independent paths finish are their angular predictions compared.
    """
    _validate_angle_tolerance(angle_tolerance_rad)
    critical_angle_result = compute_critical_clearing_angle(
        parameters,
        network,
    )
    clearing_time_result = search_smib_critical_clearing_time(
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
    return SMIBCriticalClearingCrossCheck(
        critical_angle_result=critical_angle_result,
        clearing_time_result=clearing_time_result,
        angle_tolerance_rad=angle_tolerance_rad,
    )


def _clearing_angle_rad(evaluation: SMIBClearingTimeEvaluation) -> float:
    simulation = evaluation.simulation
    t_clear_s = simulation.network.t_clear_s
    clearing_indices = [
        index
        for index, time_s in enumerate(simulation.time_s)
        if time_s == t_clear_s
    ]
    if len(clearing_indices) != 1:
        raise ValueError(
            "clearing-time trajectory must contain t_clear_s exactly once"
        )
    return float(simulation.delta_rad[clearing_indices[0]])


def _validate_angle_tolerance(angle_tolerance_rad: float) -> None:
    if not isfinite(angle_tolerance_rad) or angle_tolerance_rad < 0.0:
        raise ValueError(
            "angle_tolerance_rad must be finite and greater than or equal "
            "to zero"
        )
