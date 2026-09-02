"""Sampled first-swing assessment for the classical SMIB model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import pi

from sincrolab.models.power_angle import equilibrium_angle_rad
from sincrolab.models.smib import SMIBParameters
from sincrolab.models.transient_network import SMIBTransientNetwork
from sincrolab.simulation import SMIBTransientSimulationResult


class FirstSwingStatus(Enum):
    """Outcome of the supported forward first-swing assessment."""

    STABLE = "stable"
    UNSTABLE = "unstable"
    INDETERMINATE = "indeterminate"


class FirstSwingReason(Enum):
    """Sampled evidence that produced a first-swing status."""

    REVERSAL_BEFORE_CROSSING = "reversal_before_crossing"
    CROSSING_BEFORE_REVERSAL = "crossing_before_reversal"
    NO_POSITIVE_EXCURSION = "no_positive_excursion"
    HORIZON_ENDED_BEFORE_EVENT = "horizon_ended_before_event"
    EVENT_ORDER_AMBIGUOUS = "event_order_ambiguous"


@dataclass(frozen=True)
class FirstSwingEventBracket:
    """Two adjacent samples that bracket a first-swing event.

    The bracket records sampled evidence only. It does not imply an
    interpolated or exact continuous event time.
    """

    left_index: int
    right_index: int
    left_time_s: float
    right_time_s: float
    left_delta_rad: float
    right_delta_rad: float
    left_omega_dev_pu: float
    right_omega_dev_pu: float


@dataclass(frozen=True)
class FirstSwingAssessment:
    """Immutable sampled evidence for a classical SMIB first swing.

    ``STABLE`` means only that the first increasing postfault excursion
    reverses before reaching the associated unstable postfault equilibrium.
    It does not establish asymptotic or global stability.
    """

    status: FirstSwingStatus
    reason: FirstSwingReason
    delta_stable_post_rad: float
    delta_unstable_post_rad: float
    reversal_bracket: FirstSwingEventBracket | None
    crossing_bracket: FirstSwingEventBracket | None


def assess_smib_first_swing(
    result: SMIBTransientSimulationResult,
) -> FirstSwingAssessment:
    """Assess the sampled forward first swing of a classical SMIB trajectory.

    The supported postfault regime is
    ``0 < Pm_pu < Pmax_postfault_pu``. Reversal and unstable-equilibrium
    crossing are ordered only at the resolution of adjacent samples; no
    interpolation or root finding is performed.
    """
    parameters = result.parameters
    network = result.network
    delta_stable_post_rad, delta_unstable_post_rad = (
        _postfault_equilibrium_angles_rad(parameters, network)
    )
    clear_index = _exact_clearing_index(result, network)
    positive_excursion_index = _first_positive_speed_index(result, clear_index)

    if positive_excursion_index is None:
        return FirstSwingAssessment(
            status=FirstSwingStatus.INDETERMINATE,
            reason=FirstSwingReason.NO_POSITIVE_EXCURSION,
            delta_stable_post_rad=delta_stable_post_rad,
            delta_unstable_post_rad=delta_unstable_post_rad,
            reversal_bracket=None,
            crossing_bracket=None,
        )

    if result.delta_rad[positive_excursion_index] >= delta_unstable_post_rad:
        return FirstSwingAssessment(
            status=FirstSwingStatus.INDETERMINATE,
            reason=FirstSwingReason.EVENT_ORDER_AMBIGUOUS,
            delta_stable_post_rad=delta_stable_post_rad,
            delta_unstable_post_rad=delta_unstable_post_rad,
            reversal_bracket=None,
            crossing_bracket=None,
        )

    for left_index in range(positive_excursion_index, result.time_s.size - 1):
        right_index = left_index + 1
        reversal_observed = (
            result.omega_dev_pu[left_index] > 0.0
            and result.omega_dev_pu[right_index] <= 0.0
        )
        crossing_observed = (
            result.delta_rad[left_index] < delta_unstable_post_rad
            <= result.delta_rad[right_index]
        )

        if not reversal_observed and not crossing_observed:
            continue

        event_bracket = _event_bracket(result, left_index)
        if reversal_observed and crossing_observed:
            return FirstSwingAssessment(
                status=FirstSwingStatus.INDETERMINATE,
                reason=FirstSwingReason.EVENT_ORDER_AMBIGUOUS,
                delta_stable_post_rad=delta_stable_post_rad,
                delta_unstable_post_rad=delta_unstable_post_rad,
                reversal_bracket=event_bracket,
                crossing_bracket=event_bracket,
            )
        if crossing_observed and result.omega_dev_pu[right_index] > 0.0:
            return FirstSwingAssessment(
                status=FirstSwingStatus.UNSTABLE,
                reason=FirstSwingReason.CROSSING_BEFORE_REVERSAL,
                delta_stable_post_rad=delta_stable_post_rad,
                delta_unstable_post_rad=delta_unstable_post_rad,
                reversal_bracket=None,
                crossing_bracket=event_bracket,
            )
        if reversal_observed:
            return FirstSwingAssessment(
                status=FirstSwingStatus.STABLE,
                reason=FirstSwingReason.REVERSAL_BEFORE_CROSSING,
                delta_stable_post_rad=delta_stable_post_rad,
                delta_unstable_post_rad=delta_unstable_post_rad,
                reversal_bracket=event_bracket,
                crossing_bracket=None,
            )

    return FirstSwingAssessment(
        status=FirstSwingStatus.INDETERMINATE,
        reason=FirstSwingReason.HORIZON_ENDED_BEFORE_EVENT,
        delta_stable_post_rad=delta_stable_post_rad,
        delta_unstable_post_rad=delta_unstable_post_rad,
        reversal_bracket=None,
        crossing_bracket=None,
    )


def _postfault_equilibrium_angles_rad(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
) -> tuple[float, float]:
    Pmax_postfault_pu = network.Pmax_postfault_pu
    if not 0.0 < parameters.Pm_pu < Pmax_postfault_pu:
        raise ValueError(
            "first-swing assessment requires "
            "0 < Pm_pu < Pmax_postfault_pu"
        )

    delta_stable_post_rad = equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_pu=Pmax_postfault_pu,
    )
    return delta_stable_post_rad, pi - delta_stable_post_rad


def _exact_clearing_index(
    result: SMIBTransientSimulationResult,
    network: SMIBTransientNetwork,
) -> int:
    clearing_indices = [
        index
        for index, time_s in enumerate(result.time_s)
        if time_s == network.t_clear_s
    ]
    if len(clearing_indices) != 1:
        raise ValueError("result.time_s must contain t_clear_s exactly once")
    return clearing_indices[0]


def _first_positive_speed_index(
    result: SMIBTransientSimulationResult,
    clear_index: int,
) -> int | None:
    for index in range(clear_index, result.time_s.size):
        if result.omega_dev_pu[index] > 0.0:
            return index
    return None


def _event_bracket(
    result: SMIBTransientSimulationResult,
    left_index: int,
) -> FirstSwingEventBracket:
    right_index = left_index + 1
    return FirstSwingEventBracket(
        left_index=left_index,
        right_index=right_index,
        left_time_s=float(result.time_s[left_index]),
        right_time_s=float(result.time_s[right_index]),
        left_delta_rad=float(result.delta_rad[left_index]),
        right_delta_rad=float(result.delta_rad[right_index]),
        left_omega_dev_pu=float(result.omega_dev_pu[left_index]),
        right_omega_dev_pu=float(result.omega_dev_pu[right_index]),
    )
