"""Display contracts, with no catalog or scientific rules.

Desktop owns phase names, layout and numeric formatting. Portable owns case
content, parameter constraints, solutions, classifications and explanations.
"""

from dataclasses import dataclass


PHASES = ("Observar", "Predecir", "Simular", "Intervenir", "Comparar", "Explicar")


@dataclass(frozen=True)
class CasePreview:
    case_id: str
    title: str
    concept: str
    objective: str
    difficulty: str


@dataclass(frozen=True)
class InputField:
    key: str
    label: str
    value: float
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class QuestionView:
    key: str
    prompt: str
    options: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CaseView:
    preview: CasePreview
    context: str
    configuration: tuple[tuple[str, str], ...]
    prediction_prompt: str
    prediction_options: tuple[str, ...]
    fields: tuple[InputField, ...]
    questions: tuple[QuestionView, ...]
    hints_available: int
    has_solution: bool
    provenance: str


@dataclass(frozen=True)
class Curve:
    name: str
    time_s: tuple[float, ...]
    delta_rad: tuple[float, ...]
    omega_dev_pu: tuple[float, ...]


@dataclass(frozen=True)
class ResultView:
    status: str
    reason: str
    prediction: str
    configuration: tuple[tuple[str, str], ...]
    curves: tuple[Curve, ...]
    comparison: tuple[tuple[str, str, str], ...]
    changes: tuple[tuple[str, str, str, str], ...]
    explanation: str
    assessment: str
    debrief: str
    clearing: str


def number(value: object) -> str:
    """Format for display without changing retained portable values."""
    return format(value, ".12g") if isinstance(value, float) else str(value)
