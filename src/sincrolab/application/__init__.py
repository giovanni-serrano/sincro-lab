"""Application use cases shared by SincroLab interfaces."""

from sincrolab.application.results import (
    SMIBSimulationResult,
    SMIBTransientSimulationResult,
)
from sincrolab.application.transient import simulate_smib_transient
from sincrolab.application.clearing_time import (
    SMIBClearingTimeEvaluation,
    SMIBCriticalClearingTimeResult,
    evaluate_smib_clearing_time,
    search_smib_critical_clearing_time,
)
from sincrolab.application.critical_clearing_cross_check import (
    SMIBCriticalClearingCrossCheck,
    cross_check_smib_critical_clearing,
)
from sincrolab.application.equilibrium import (
    simulate_smib_equilibrium,
    simulate_smib_free_disturbance,
)
from sincrolab.application.learning import (
    ExplanationEvidence,
    ExplanationKind,
    LearningConcept,
    PedagogicalExplanation,
    explain_critical_clearing_cross_check,
    explain_critical_clearing_time,
    explain_first_swing,
    explain_time_step_sensitivity,
    render_explanation_text,
)

__all__ = [
    "SMIBClearingTimeEvaluation",
    "SMIBCriticalClearingTimeResult",
    "SMIBCriticalClearingCrossCheck",
    "SMIBSimulationResult",
    "SMIBTransientSimulationResult",
    "ExplanationEvidence",
    "ExplanationKind",
    "LearningConcept",
    "PedagogicalExplanation",
    "evaluate_smib_clearing_time",
    "cross_check_smib_critical_clearing",
    "explain_critical_clearing_cross_check",
    "explain_critical_clearing_time",
    "explain_first_swing",
    "explain_time_step_sensitivity",
    "render_explanation_text",
    "search_smib_critical_clearing_time",
    "simulate_smib_equilibrium",
    "simulate_smib_free_disturbance",
    "simulate_smib_transient",
]
