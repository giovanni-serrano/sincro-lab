"""Structured results returned by SMIB application use cases."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class SMIBSimulationResult:
    """Immutable snapshot of a classical SMIB trajectory.

    Attributes:
        time_s: Strictly increasing time samples in seconds.
        delta_rad: Electrical rotor angle in radians at each sample.
        omega_dev_pu: Per-unit synchronous-speed deviation at each sample.

    All series are independent, read-only float64 vectors with the same
    nonzero length.
    """

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

        if not (
            time_s.size == delta_rad.size == omega_dev_pu.size
        ):
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
