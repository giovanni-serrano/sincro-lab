"""Application use cases shared by SincroLab interfaces."""

from sincrolab.application.results import (
    SMIBSimulationResult,
    SMIBTransientSimulationResult,
)
from sincrolab.application.transient import simulate_smib_transient
from sincrolab.application.equilibrium import (
    simulate_smib_equilibrium,
    simulate_smib_free_disturbance,
)

__all__ = [
    "SMIBSimulationResult",
    "SMIBTransientSimulationResult",
    "simulate_smib_equilibrium",
    "simulate_smib_free_disturbance",
    "simulate_smib_transient",
]
