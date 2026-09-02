"""Equal-area analysis for a compatible classical SMIB first swing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, pi

from sincrolab.models.power_angle import (
    electrical_power_pu,
    equilibrium_angle_rad,
    initial_equilibrium_angle_rad,
)
from sincrolab.models.smib import SMIBParameters
from sincrolab.models.transient_network import SMIBTransientNetwork


DEFAULT_AREA_TOLERANCE_PU_RAD = 1e-12
"""Absolute float64 comparison tolerance for ordinary-scale V0.1 cases.

The tolerance covers rounding in the closed-form area expressions; it is not
a universal physical tolerance.
"""


class EqualAreaStatus(Enum):
    """Energy-balance outcome for the supplied clearing angle."""

    STABLE = "stable"
    AT_LIMIT = "at_limit"
    UNSTABLE = "unstable"


@dataclass(frozen=True)
class EqualAreaAssessment:
    """Immutable equal-area evidence for a specified clearing angle.

    Every accelerating or decelerating area is a nonnegative magnitude in
    pu rad. The total accelerating area includes the fault contribution and,
    when clearing precedes the stable postfault equilibrium, the additional
    postfault acceleration. ``AT_LIMIT`` denotes balance within
    ``area_tolerance_pu_rad``; this API assesses a supplied angle and does not
    solve for a critical angle.
    """

    status: EqualAreaStatus
    delta_initial_rad: float
    delta_clear_rad: float
    delta_stable_post_rad: float
    delta_unstable_post_rad: float
    fault_accelerating_area_pu_rad: float
    postfault_accelerating_area_pu_rad: float
    total_accelerating_area_pu_rad: float
    decelerating_area_available_pu_rad: float
    area_margin_pu_rad: float
    area_tolerance_pu_rad: float


def assess_equal_area(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
    *,
    delta_clear_rad: float,
    area_tolerance_pu_rad: float = DEFAULT_AREA_TOLERANCE_PU_RAD,
) -> EqualAreaAssessment:
    """Assess the classical SMIB equal-area balance at ``delta_clear_rad``.

    The supported regime assumes constant mechanical power, sinusoidal
    power-angle curves with constant ``Pmax_pu`` in each network state, zero
    damping, and a forward first swing. Areas are evaluated analytically and
    do not use a time-domain trajectory or integrator.
    """
    _validate_scalar_inputs(
        parameters,
        delta_clear_rad=delta_clear_rad,
        area_tolerance_pu_rad=area_tolerance_pu_rad,
    )
    _validate_supported_power_regime(parameters, network)

    delta_initial_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=network.Pmax_prefault_pu,
    )
    delta_stable_post_rad = equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_pu=network.Pmax_postfault_pu,
    )
    delta_unstable_post_rad = pi - delta_stable_post_rad
    _validate_clearing_angle(
        delta_clear_rad=delta_clear_rad,
        delta_initial_rad=delta_initial_rad,
        delta_unstable_post_rad=delta_unstable_post_rad,
    )
    _validate_fault_acceleration(
        parameters,
        network,
        delta_initial_rad=delta_initial_rad,
        delta_clear_rad=delta_clear_rad,
    )

    fault_accelerating_area_pu_rad = _fault_accelerating_area_pu_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_fault_pu=network.Pmax_fault_pu,
        delta_initial_rad=delta_initial_rad,
        delta_clear_rad=delta_clear_rad,
    )
    postfault_accelerating_area_pu_rad = (
        _postfault_accelerating_area_pu_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_postfault_pu=network.Pmax_postfault_pu,
            delta_clear_rad=delta_clear_rad,
            delta_stable_post_rad=delta_stable_post_rad,
        )
    )
    total_accelerating_area_pu_rad = (
        fault_accelerating_area_pu_rad
        + postfault_accelerating_area_pu_rad
    )
    delta_deceleration_start_rad = max(
        delta_clear_rad,
        delta_stable_post_rad,
    )
    decelerating_area_available_pu_rad = (
        _decelerating_area_available_pu_rad(
            Pm_pu=parameters.Pm_pu,
            Pmax_postfault_pu=network.Pmax_postfault_pu,
            delta_deceleration_start_rad=delta_deceleration_start_rad,
            delta_unstable_post_rad=delta_unstable_post_rad,
        )
    )
    if fault_accelerating_area_pu_rad < 0.0:
        raise ValueError(
            "fault interval must have a nonnegative accelerating area"
        )
    if postfault_accelerating_area_pu_rad < 0.0:
        raise ValueError(
            "postfault accelerating area must be nonnegative"
        )
    if decelerating_area_available_pu_rad < 0.0:
        raise ValueError(
            "postfault decelerating area must be nonnegative"
        )

    area_margin_pu_rad = (
        decelerating_area_available_pu_rad
        - total_accelerating_area_pu_rad
    )
    if area_margin_pu_rad > area_tolerance_pu_rad:
        status = EqualAreaStatus.STABLE
    elif area_margin_pu_rad < -area_tolerance_pu_rad:
        status = EqualAreaStatus.UNSTABLE
    else:
        status = EqualAreaStatus.AT_LIMIT

    return EqualAreaAssessment(
        status=status,
        delta_initial_rad=delta_initial_rad,
        delta_clear_rad=delta_clear_rad,
        delta_stable_post_rad=delta_stable_post_rad,
        delta_unstable_post_rad=delta_unstable_post_rad,
        fault_accelerating_area_pu_rad=fault_accelerating_area_pu_rad,
        postfault_accelerating_area_pu_rad=(
            postfault_accelerating_area_pu_rad
        ),
        total_accelerating_area_pu_rad=total_accelerating_area_pu_rad,
        decelerating_area_available_pu_rad=(
            decelerating_area_available_pu_rad
        ),
        area_margin_pu_rad=area_margin_pu_rad,
        area_tolerance_pu_rad=area_tolerance_pu_rad,
    )


def _validate_scalar_inputs(
    parameters: SMIBParameters,
    *,
    delta_clear_rad: float,
    area_tolerance_pu_rad: float,
) -> None:
    if parameters.D_pu != 0.0:
        raise ValueError("equal-area assessment requires D_pu == 0")
    if not isfinite(delta_clear_rad):
        raise ValueError("delta_clear_rad must be finite")
    if (
        not isfinite(area_tolerance_pu_rad)
        or area_tolerance_pu_rad < 0.0
    ):
        raise ValueError(
            "area_tolerance_pu_rad must be finite and greater than or equal "
            "to zero"
        )


def _validate_supported_power_regime(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
) -> None:
    if not 0.0 < parameters.Pm_pu < network.Pmax_prefault_pu:
        raise ValueError(
            "equal-area assessment requires "
            "0 < Pm_pu < Pmax_prefault_pu"
        )
    if not 0.0 < parameters.Pm_pu < network.Pmax_postfault_pu:
        raise ValueError(
            "equal-area assessment requires "
            "0 < Pm_pu < Pmax_postfault_pu"
        )


def _validate_clearing_angle(
    *,
    delta_clear_rad: float,
    delta_initial_rad: float,
    delta_unstable_post_rad: float,
) -> None:
    if delta_clear_rad < delta_initial_rad:
        raise ValueError(
            "delta_clear_rad must be greater than or equal to "
            "delta_initial_rad"
        )
    if delta_clear_rad >= delta_unstable_post_rad:
        raise ValueError(
            "delta_clear_rad must be less than delta_unstable_post_rad"
        )


def _validate_fault_acceleration(
    parameters: SMIBParameters,
    network: SMIBTransientNetwork,
    *,
    delta_initial_rad: float,
    delta_clear_rad: float,
) -> None:
    if delta_clear_rad == delta_initial_rad:
        return

    # delta_initial lies in (0, pi/2). The maximum of sin(delta) over the
    # supported forward interval occurs at min(delta_clear, pi/2).
    peak_fault_power_pu = electrical_power_pu(
        delta_rad=min(delta_clear_rad, pi / 2.0),
        Pmax_pu=network.Pmax_fault_pu,
    )
    if peak_fault_power_pu > parameters.Pm_pu:
        raise ValueError(
            "fault interval must have nonnegative accelerating power "
            "through delta_clear_rad"
        )


def _fault_accelerating_area_pu_rad(
    *,
    Pm_pu: float,
    Pmax_fault_pu: float,
    delta_initial_rad: float,
    delta_clear_rad: float,
) -> float:
    """Integrate ``Pm - Pe_fault`` from initial to clearing angle."""
    return (
        Pm_pu * (delta_clear_rad - delta_initial_rad)
        + Pmax_fault_pu
        * (cos(delta_clear_rad) - cos(delta_initial_rad))
    )


def _postfault_accelerating_area_pu_rad(
    *,
    Pm_pu: float,
    Pmax_postfault_pu: float,
    delta_clear_rad: float,
    delta_stable_post_rad: float,
) -> float:
    """Integrate postfault acceleration up to the stable equilibrium."""
    if delta_clear_rad >= delta_stable_post_rad:
        return 0.0

    return (
        Pm_pu * (delta_stable_post_rad - delta_clear_rad)
        + Pmax_postfault_pu
        * (cos(delta_stable_post_rad) - cos(delta_clear_rad))
    )


def _decelerating_area_available_pu_rad(
    *,
    Pm_pu: float,
    Pmax_postfault_pu: float,
    delta_deceleration_start_rad: float,
    delta_unstable_post_rad: float,
) -> float:
    """Integrate postfault deceleration up to the unstable equilibrium."""
    return (
        Pmax_postfault_pu
        * (
            cos(delta_deceleration_start_rad)
            - cos(delta_unstable_post_rad)
        )
        - Pm_pu
        * (delta_unstable_post_rad - delta_deceleration_start_rad)
    )
