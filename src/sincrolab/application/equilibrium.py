"""Application use cases for continuous, constant-parameter SMIB motion."""

from functools import partial
from math import isfinite

import numpy as np

from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    initial_equilibrium_angle_rad,
    smib_swing_rhs,
)
from sincrolab.numerical import classical_rk4
from sincrolab.simulation import SMIBSimulationResult


def simulate_smib_equilibrium(
    parameters: SMIBParameters,
    *,
    Pmax_pu: float,
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
        Pmax_prefault_pu=Pmax_pu,
    )
    initial_state = SMIBInitialState(
        delta_rad=delta0_rad,
        omega_dev_pu=0.0,
    )

    return _simulate_smib_from_initial_state(
        parameters,
        initial_state,
        Pmax_pu=Pmax_pu,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )


def simulate_smib_free_disturbance(
    parameters: SMIBParameters,
    *,
    Pmax_pu: float,
    delta_offset_rad: float,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBSimulationResult:
    """Integrate free motion after an initial rotor-angle displacement.

    The offset is added to the principal equilibrium angle in radians. Speed
    deviation starts at zero, and all physical parameters remain constant.
    """
    delta0_rad = initial_equilibrium_angle_rad(
        Pm_pu=parameters.Pm_pu,
        Pmax_prefault_pu=Pmax_pu,
    )
    if not isfinite(delta_offset_rad):
        raise ValueError("delta_offset_rad must be finite")

    initial_state = SMIBInitialState(
        delta_rad=delta0_rad + delta_offset_rad,
        omega_dev_pu=0.0,
    )

    return _simulate_smib_from_initial_state(
        parameters,
        initial_state,
        Pmax_pu=Pmax_pu,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )


def _simulate_smib_from_initial_state(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    *,
    Pmax_pu: float,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBSimulationResult:
    state_vector = np.array(
        [initial_state.delta_rad, initial_state.omega_dev_pu],
        dtype=np.float64,
    )
    rhs = partial(
        smib_swing_rhs,
        parameters=parameters,
        Pmax_pu=Pmax_pu,
    )

    time_s, states = classical_rk4(
        rhs=rhs,
        y0=state_vector,
        t_start=t_start_s,
        t_end=t_end_s,
        dt=dt_s,
    )

    return SMIBSimulationResult(
        time_s=time_s,
        delta_rad=states[:, 0],
        omega_dev_pu=states[:, 1],
    )
