"""Neutral trajectory and provenance types shared by application and analysis."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sincrolab.models.smib import SMIBInitialState, SMIBParameters
from sincrolab.models.transient_network import SMIBTransientNetwork


@dataclass(frozen=True)
class SMIBSimulationResult:
    """Immutable snapshot of a classical SMIB trajectory."""

    time_s: NDArray[np.float64]
    delta_rad: NDArray[np.float64]
    omega_dev_pu: NDArray[np.float64]

    def __post_init__(self) -> None:
        time_s = _as_float64_vector("time_s", self.time_s)
        delta_rad = _as_float64_vector("delta_rad", self.delta_rad)
        omega_dev_pu = _as_float64_vector(
            "omega_dev_pu",
            self.omega_dev_pu,
        )

        if not time_s.size == delta_rad.size == omega_dev_pu.size:
            raise ValueError("result series must have the same length")
        if time_s.size == 0:
            raise ValueError("result series must contain at least one sample")
        if time_s.size > 1 and not np.all(np.diff(time_s) > 0.0):
            raise ValueError("time_s must be strictly increasing")

        for name, values in (
            ("time_s", time_s),
            ("delta_rad", delta_rad),
            ("omega_dev_pu", omega_dev_pu),
        ):
            values.setflags(write=False)
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class SMIBTransientSimulationResult:
    """Transient trajectory inseparable from its immutable configuration."""

    trajectory: SMIBSimulationResult
    parameters: SMIBParameters
    initial_state: SMIBInitialState
    network: SMIBTransientNetwork
    t_start_s: float
    t_end_s: float
    dt_s: float

    @property
    def time_s(self) -> NDArray[np.float64]:
        return self.trajectory.time_s

    @property
    def delta_rad(self) -> NDArray[np.float64]:
        return self.trajectory.delta_rad

    @property
    def omega_dev_pu(self) -> NDArray[np.float64]:
        return self.trajectory.omega_dev_pu


def _as_float64_vector(
    name: str,
    values: NDArray[np.float64],
) -> NDArray[np.float64]:
    values_array = np.asarray(values, dtype=np.float64)
    if values_array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.all(np.isfinite(values_array)):
        raise ValueError(f"{name} values must be finite")

    # The immutable bytes backing prevents callers from re-enabling writes,
    # while also ensuring the snapshot cannot alias its input.
    return np.frombuffer(values_array.tobytes(), dtype=np.float64)
