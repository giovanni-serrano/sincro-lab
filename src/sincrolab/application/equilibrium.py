"""Application use case for an unperturbed SMIB equilibrium simulation."""

from dataclasses import dataclass
from functools import partial

import numpy as np
from numpy.typing import NDArray

from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)
from sincrolab.numerical import classical_rk4


@dataclass(frozen=True)
class SMIBSimulationResult:
    """Structured trajectory of the classical SMIB state.

    Attributes:
        time_s: Time samples in seconds.
        delta_rad: Electrical rotor angle in radians at each sample.
        omega_dev_pu: Per-unit speed deviation at each sample.
    """

    time_s: NDArray[np.float64]
    delta_rad: NDArray[np.float64]
    omega_dev_pu: NDArray[np.float64]


def simulate_smib_equilibrium(
    parameters: SMIBParameters,
    *,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBSimulationResult:
    """Integrate an unperturbed SMIB from its principal equilibrium point.

    All temporal arguments are expressed in seconds. Their validation is
    delegated to the fixed-step RK4 integrator.
    """
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=parameters.Pmax_pu,
    )
    initial_state = SMIBInitialState(
        delta_rad=delta0_rad,
        omega_dev_pu=0.0,
    )
    state_vector = np.array(
        [initial_state.delta_rad, initial_state.omega_dev_pu],
        dtype=np.float64,
    )
    rhs = partial(smib_swing_rhs, parameters=parameters)

    time_s, states = classical_rk4(
        rhs=rhs,
        y0=state_vector,
        t_start=t_start_s,
        t_end=t_end_s,
        dt=dt_s,
    )

    return SMIBSimulationResult(
        time_s=np.array(time_s, dtype=np.float64, copy=True),
        delta_rad=np.array(states[:, 0], dtype=np.float64, copy=True),
        omega_dev_pu=np.array(states[:, 1], dtype=np.float64, copy=True),
    )
