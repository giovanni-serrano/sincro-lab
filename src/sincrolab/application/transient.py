"""Application orchestration for piecewise-constant SMIB disturbances."""

from functools import partial
from math import isfinite

import numpy as np

from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
    smib_swing_rhs,
)
from sincrolab.numerical import classical_rk4
from sincrolab.simulation import (
    SMIBSimulationResult,
    SMIBTransientSimulationResult,
)


def simulate_smib_transient(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    network: SMIBTransientNetwork,
    *,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBTransientSimulationResult:
    """Integrate a complete prefault, fault, and postfault SMIB sequence.

    Each interval uses a separate RK4 call with constant network physics. The
    mechanical state is transported unchanged across both event boundaries.
    """
    _validate_horizon(
        network,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
    )

    current_state = np.array(
        [initial_state.delta_rad, initial_state.omega_dev_pu],
        dtype=np.float64,
    )
    segments = (
        (t_start_s, network.t_fault_s, network.Pmax_prefault_pu),
        (network.t_fault_s, network.t_clear_s, network.Pmax_fault_pu),
        (network.t_clear_s, t_end_s, network.Pmax_postfault_pu),
    )
    time_parts: list[np.ndarray] = []
    state_parts: list[np.ndarray] = []

    for segment_index, (segment_start_s, segment_end_s, Pmax_pu) in enumerate(
        segments
    ):
        rhs = partial(
            smib_swing_rhs,
            parameters=parameters,
            Pmax_pu=Pmax_pu,
        )
        segment_time_s, segment_states = classical_rk4(
            rhs=rhs,
            y0=current_state,
            t_start=segment_start_s,
            t_end=segment_end_s,
            dt=dt_s,
        )

        current_state = np.array(segment_states[-1], dtype=np.float64, copy=True)
        # The previous segment already stores the shared boundary state. The
        # next segment starts from that same state, so omitting its first row
        # keeps each physical event exactly once without a generic dedup pass.
        first_sample = 0 if segment_index == 0 else 1
        time_parts.append(segment_time_s[first_sample:])
        state_parts.append(segment_states[first_sample:])

    time_s = np.concatenate(time_parts)
    states = np.concatenate(state_parts, axis=0)
    return SMIBTransientSimulationResult(
        trajectory=SMIBSimulationResult(
            time_s=time_s,
            delta_rad=states[:, 0],
            omega_dev_pu=states[:, 1],
        ),
        parameters=parameters,
        initial_state=initial_state,
        network=network,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )


def _validate_horizon(
    network: SMIBTransientNetwork,
    *,
    t_start_s: float,
    t_end_s: float,
) -> None:
    if not isfinite(t_start_s) or not isfinite(t_end_s):
        raise ValueError("t_start_s and t_end_s must be finite")
    if t_start_s > network.t_fault_s:
        raise ValueError("t_start_s must be less than or equal to t_fault_s")
    if t_end_s < network.t_clear_s:
        raise ValueError("t_end_s must be greater than or equal to t_clear_s")
