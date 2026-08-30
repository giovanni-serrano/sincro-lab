"""Equivalent network states for a classical SMIB transient scenario."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class SMIBNetworkState(Enum):
    """Discrete electrical-network state of the transient sequence."""

    PREFAULT = "prefault"
    FAULT = "fault"
    POSTFAULT = "postfault"


@dataclass(frozen=True)
class SMIBTransientNetwork:
    """Equivalent transfer limits and event times for an SMIB disturbance.

    The network is represented pedagogically by a piecewise change in
    ``Pmax_pu``; this is not a general short-circuit or network model.
    ``t_fault_s`` belongs to the fault interval and ``t_clear_s`` belongs to
    the postfault interval.
    """

    Pmax_prefault_pu: float
    Pmax_fault_pu: float
    Pmax_postfault_pu: float
    t_fault_s: float
    t_clear_s: float

    def __post_init__(self) -> None:
        _require_positive_finite("Pmax_prefault_pu", self.Pmax_prefault_pu)
        _require_nonnegative_finite("Pmax_fault_pu", self.Pmax_fault_pu)
        _require_positive_finite("Pmax_postfault_pu", self.Pmax_postfault_pu)
        _require_nonnegative_finite("t_fault_s", self.t_fault_s)
        if not isfinite(self.t_clear_s) or self.t_clear_s <= self.t_fault_s:
            raise ValueError(
                "t_clear_s must be finite and greater than t_fault_s"
            )

    def state_at(self, time_s: float) -> SMIBNetworkState:
        """Return the network state active at a finite time in seconds."""
        _require_finite("time_s", time_s)

        if time_s < self.t_fault_s:
            return SMIBNetworkState.PREFAULT
        if time_s < self.t_clear_s:
            return SMIBNetworkState.FAULT
        return SMIBNetworkState.POSTFAULT

    def Pmax_at(self, time_s: float) -> float:
        """Return the equivalent transfer capability active at ``time_s``."""
        state = self.state_at(time_s)
        if state is SMIBNetworkState.PREFAULT:
            return self.Pmax_prefault_pu
        if state is SMIBNetworkState.FAULT:
            return self.Pmax_fault_pu
        return self.Pmax_postfault_pu


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_nonnegative_finite(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0:
        raise ValueError(
            f"{name} must be finite and greater than or equal to zero"
        )


def _require_positive_finite(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
