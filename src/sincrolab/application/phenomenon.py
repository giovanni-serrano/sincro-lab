"""Beginner teaching projections of the unchanged portable SMIB experiment.

This module interprets an existing diagnosis; it never classifies a trajectory.
Display windows select original samples and do not affect the evaluation.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sincrolab.application.portable import TransientLabRunDTO


def prepare_transfer(count: int, used_choice_indices: Sequence[int]) -> dict[str, object]:
    """Choose an unseen interior input, without simulating or inspecting outcomes."""
    if not isinstance(used_choice_indices, (list, tuple)) or any(
        type(index) is not int or not 0 <= index < count
        for index in used_choice_indices
    ):
        raise ValueError("Expected previously used clearing choice indices")
    candidates = sorted(range(1, count - 1), key=lambda index: abs(index - count // 2))
    choice = next((index for index in candidates if index not in used_choice_indices), None)
    return {
        "choice_index": choice,
        "prompt": "Ahora prueba una duración que aún no has observado. "
        "La máquina y la red conservan sus parámetros. ¿Qué esperas que ocurra "
        "con la separación respecto de la red? Predice y explica tu intuición.",
    }


def explain_run(run: TransientLabRunDTO) -> dict[str, object]:
    """Connect a recorded prediction to sampled evidence and staged language."""
    evaluation = run.evaluation
    diagnosis = evaluation.first_swing
    trajectory = evaluation.trajectory
    config = evaluation.configuration
    predictions = {
        "maintain": "Mantendrá sincronismo",
        "lose": "Perderá sincronismo",
        "unsure": "No estoy seguro",
    }
    outcomes = {
        "stable": "La separación deja de crecer y comienza a volver. "
        "Mantiene sincronismo en la primera oscilación evaluada.",
        "unstable": "La separación alcanza la frontera posfalla antes de volver. "
        "Pierde sincronismo según el criterio de primera oscilación.",
        "indeterminate": "La evidencia muestreada no permite decidir el resultado "
        "de la primera oscilación.",
    }
    expected_status = {"maintain": "stable", "lose": "unstable"}.get(run.prediction)
    if diagnosis.status == "indeterminate":
        confrontation = "Esta ejecución no permite confirmar ni descartar tu expectativa."
    elif expected_status is None:
        confrontation = "Ahora tienes evidencia para formular una expectativa más concreta."
    elif expected_status == diagnosis.status:
        confrontation = "Lo observado coincide con tu predicción bajo este criterio."
    else:
        confrontation = "Lo observado difiere de tu predicción. Revisa dónde cambia el movimiento."

    bracket = (diagnosis.reversal_bracket if diagnosis.status == "stable" else
               diagnosis.crossing_bracket if diagnosis.status == "unstable" else None)
    evidence = evaluation.explanation.summary
    end_index = len(trajectory.time_s) - 1
    if bracket is not None:
        event = "La velocidad relativa pasa de positiva a no positiva" if diagnosis.status == "stable" else (
            "Se cruza el equilibrio inestable posfalla con velocidad relativa positiva")
        evidence = (f"{event} entre {bracket.left_time_s:.3f} y "
                    f"{bracket.right_time_s:.3f} s. "
                    f"Velocidad relativa: {bracket.left_omega_dev_pu:.6f} → "
                    f"{bracket.right_omega_dev_pu:.6f} pu. "
                    "El intervalo conserva las dos muestras originales; no es un instante exacto.")
        # A 0.15 s display margin exposes motion after the diagnosed event.
        # This is a viewport choice, never a classification or solver tolerance.
        end_index = min(end_index, bisect_left(trajectory.time_s, bracket.right_time_s + 0.15))
    clearing_index = trajectory.time_s.index(config.network.t_clear_s)
    return {
        "prediction": predictions[run.prediction],
        "outcome": outcomes[diagnosis.status],
        "confrontation": confrontation,
        "evidence": evidence,
        "event_bracket": bracket.to_dict() if bracket is not None else None,
        "first_swing_end_index": end_index,
        "clearing_index": clearing_index,
        "clearing_evidence": (
            f"Falla durante {run.fault_duration_s:.3f} s; despeje en "
            f"{config.network.t_clear_s:.3f} s. Al despejar: separación "
            f"{run.angle_deg[clearing_index]:.2f}°, velocidad relativa "
            f"{trajectory.omega_dev_pu[clearing_index]:.6f} pu."
        ),
        "why": "Despejar cambia la capacidad de transferencia eléctrica. "
        "El ángulo y la velocidad conservan continuidad: el rotor puede seguir "
        "avanzando respecto de la red mientras su velocidad relativa disminuye.",
        "stages": _stages(),
        "transfer_reflection": "Compara el estado al despejar con A. "
        "¿Qué evidencia te haría cambiar tu explicación? Describe cómo la duración "
        "de la falla cambió el balance de potencias, la velocidad relativa y la separación.",
        "limitation": list(run.evaluation.explanation.limitations),
    }


def _stages() -> list[dict[str, str]]:
    """Physical meanings before notation, with the full damped model last."""
    return [
        {"id": "physical", "title": "1 · Una entrada y una salida",
         "text": "El generador recibe potencia mecánica y transfiere potencia eléctrica a la red. "
         "La falla de este experimento reduce la capacidad de transferencia eléctrica. "
         "La entrada mecánica se mantiene. Observa ambas potencias en el mismo instante.",
         "question": "En el primer despeje, ¿qué cambió en cada corrida?"},
        {"id": "powers", "title": "2 · Nombrar lo que observaste",
         "text": "Pm es la potencia mecánica de entrada al rotor. Pe es la potencia eléctrica "
         "transferida según la red y la separación angular actuales. Ambas se expresan "
         "en per unit (pu), respecto de una misma potencia base.",
         "question": "Recorre la falla: ¿cuál de las dos potencias es mayor?"},
        {"id": "balance", "title": "3 · El balance de potencias",
         "text": "Pa = Pm − Pe. Pa positiva indica entrada mecánica mayor que transferencia "
         "eléctrica; Pa negativa indica lo contrario. Pa es potencia, no energía ni velocidad. "
         "Aquí hay amortiguamiento: para conocer el cambio de velocidad también se debe "
         "considerar la potencia asociada al amortiguamiento.",
         "question": "¿Basta mirar la diferencia de potencias para saber la posición del rotor?"},
        {"id": "speed", "title": "4 · Primero cambia la velocidad relativa",
         "text": "Δω es la desviación de velocidad eléctrica respecto de la referencia "
         "síncrona, en pu. El balance neto, después del término de amortiguamiento, "
         "determina si Δω aumenta o disminuye. Disminuir Δω no significa que ya sea "
         "negativa: el rotor puede seguir adelantándose mientras desacelera relativamente.",
         "question": "Busca un instante después del despeje: ¿la separación sigue creciendo?"},
        {"id": "angle", "title": "5 · Después cambia la separación angular",
         "text": "δ es el ángulo eléctrico del rotor respecto de la referencia síncrona. "
         "Acumula el efecto de la velocidad relativa: crece con Δω positiva y disminuye "
         "con Δω negativa. Volver en esta vista no significa invertir el giro mecánico. "
         "Permanecer sincronizado permite oscilaciones de esa separación sin un alejamiento "
         "continuo; el diagnóstico aquí evalúa solo la primera excursión.",
         "question": "¿Por qué el despeje no devuelve inmediatamente el ángulo a su valor inicial?"},
        {"id": "equations", "title": "6 · La ecuación describe ese movimiento",
         "text": "d(Δω)/dt = (Pm − Pe − D·Δω)/(2H)\ndδ/dt = ωs·Δω\n"
         "Pe = Pmax del estado de red · sen(δ)\n"
         "Estas son las ecuaciones del modelo clásico SMIB que acabas de observar. "
         "El balance neto cambia la velocidad relativa; esta cambia el ángulo. "
         "H es la constante de inercia (s); D·Δω es potencia de amortiguamiento (pu); "
         "ωs = 2π·f_base es la velocidad síncrona eléctrica (rad/s). "
         "Internamente δ está en radianes; la gráfica lo muestra en grados. El tiempo está "
         "en segundos. Pmax cambia exactamente al aplicar y despejar la falla equivalente. "
         "El diagnóstico de primera oscilación usa el orden de reversión y cruce de la "
         "frontera posfalla; no una regla universal de 180° ni una garantía global.",
         "question": "Ahora que conoces la causa, prueba una duración que todavía no has visto."},
    ]
