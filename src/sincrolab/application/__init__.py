"""Application use cases shared by SincroLab interfaces."""

from sincrolab.application.equilibrium import (
    SMIBSimulationResult,
    simulate_smib_equilibrium,
    simulate_smib_free_disturbance,
)

__all__ = [
    "SMIBSimulationResult",
    "simulate_smib_equilibrium",
    "simulate_smib_free_disturbance",
]
