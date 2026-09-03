"""Application evaluation of one specified SMIB clearing time."""

from dataclasses import dataclass, replace

from sincrolab.analysis.first_swing import (
    FirstSwingAssessment,
    assess_smib_first_swing,
)
from sincrolab.application.transient import simulate_smib_transient
from sincrolab.models import (
    SMIBInitialState,
    SMIBParameters,
    SMIBTransientNetwork,
)
from sincrolab.simulation import SMIBTransientSimulationResult


@dataclass(frozen=True)
class SMIBClearingTimeEvaluation:
    """Immutable composition of a transient run and its first-swing result."""

    simulation: SMIBTransientSimulationResult
    first_swing: FirstSwingAssessment


def evaluate_smib_clearing_time(
    parameters: SMIBParameters,
    initial_state: SMIBInitialState,
    network: SMIBTransientNetwork,
    *,
    t_clear_s: float,
    t_start_s: float,
    t_end_s: float,
    dt_s: float,
) -> SMIBClearingTimeEvaluation:
    """Simulate and assess one clearing time with explicit temporal settings.

    The supplied network is not mutated. Its transfer capabilities and fault
    onset are preserved while ``t_clear_s`` is replaced in a new value object.
    """
    effective_network = replace(network, t_clear_s=t_clear_s)
    if t_end_s <= effective_network.t_clear_s:
        raise ValueError(
            "t_end_s must be greater than t_clear_s for first-swing assessment"
        )

    simulation = simulate_smib_transient(
        parameters,
        initial_state,
        effective_network,
        t_start_s=t_start_s,
        t_end_s=t_end_s,
        dt_s=dt_s,
    )
    return SMIBClearingTimeEvaluation(
        simulation=simulation,
        first_swing=assess_smib_first_swing(simulation),
    )
