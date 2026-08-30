"""Value objects for the classical single-machine infinite-bus model."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SMIBParameters:
    """Physical parameters of the classical SMIB model on a common pu base.

    Attributes:
        H_s: Inertia constant in seconds.
        D_pu: Damping-power coefficient in pu power per pu speed deviation.
        f_base_hz: Electrical base frequency in hertz.
        Pm_pu: Constant mechanical input power in per unit.
        Pmax_pu: Power-angle capability in per unit for
            ``Pe_pu = Pmax_pu * sin(delta_rad)``.
    """

    H_s: float
    D_pu: float
    f_base_hz: float
    Pm_pu: float
    Pmax_pu: float

    def __post_init__(self) -> None:
        _require_positive_finite("H_s", self.H_s)
        _require_finite("D_pu", self.D_pu)
        _require_positive_finite("f_base_hz", self.f_base_hz)
        _require_finite("Pm_pu", self.Pm_pu)
        _require_positive_finite("Pmax_pu", self.Pmax_pu)


@dataclass(frozen=True)
class SMIBInitialState:
    """Initial state of the classical SMIB model.

    Attributes:
        delta_rad: Electrical rotor angle relative to the infinite bus, in
            radians.
        omega_dev_pu: Rotor speed deviation from synchronous speed, in per
            unit. Synchronous speed corresponds to zero deviation.
    """

    delta_rad: float
    omega_dev_pu: float

    def __post_init__(self) -> None:
        _require_finite("delta_rad", self.delta_rad)
        _require_finite("omega_dev_pu", self.omega_dev_pu)


def _require_finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_positive_finite(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
