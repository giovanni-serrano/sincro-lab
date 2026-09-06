"""Small editorial previews for H27, not executable guided-case definitions.

IDs anticipate existing guided cases, but these entries contain no configuration,
answers, hints or derived evidence. H28 will connect the portable application API.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CasePreview:
    """Display-only metadata used by the home, browser and detail views."""

    case_id: str
    title: str
    concept: str
    objective: str
    difficulty: str


CASE_PREVIEWS = (
    CasePreview(
        "late-clearing-bracket",
        "El tiempo de despeje",
        "Duración de la perturbación",
        "Relacionar el momento del despeje con la respuesta del rotor y explorar "
        "el intervalo de transición entre resultados.",
        "Introductorio",
    ),
    CasePreview(
        "controlled-inertia-effect",
        "El papel de la inercia",
        "Comparación controlada",
        "Comparar la respuesta del rotor al cambiar únicamente la inercia "
        "y conservar las demás condiciones del caso.",
        "Intermedio",
    ),
    CasePreview(
        "first-swing-event-evidence",
        "Leer la primera oscilación",
        "Evidencia en la trayectoria",
        "Distinguir resultados mediante el orden de los eventos y la evidencia "
        "de ángulo y velocidad del rotor.",
        "Introductorio",
    ),
)
