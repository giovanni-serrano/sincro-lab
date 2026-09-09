"""Shared product semantics without altering scientific or request contracts."""

import ast
from dataclasses import FrozenInstanceError, fields, replace
import json
from pathlib import Path
import re

import pytest

from sincrolab.application import learning_content as content, portable
from sincrolab.application.guided_learning import default_guided_cases
from sincrolab.interfaces.desktop.adapter import DesktopController
from sincrolab.interfaces.web.bridge import dispatch


ROOT = Path(__file__).parents[1]
LEARNING_ORDER = (
    "first-swing-event-evidence", "late-clearing-bracket", "controlled-inertia-effect",
)
RAW_TERMS = re.compile(
    r"\b(?:H15|H19|H24|H25|H_s|D_pu|f_base_hz|Pm_pu|delta_rad|omega_dev_pu|"
    r"Pmax_prefault_pu|Pmax_fault_pu|Pmax_postfault_pu)\b"
)


def visible_strings(value):
    """Inspect deliberately visible fields, not internal IDs or enum values."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from visible_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "title", "label", "description", "paragraphs", "observe", "intervene",
                "compare", "explain", "context", "learning_objective", "prediction_prompt",
                "prompt", "text", "summary", "statement", "limitations", "limitation",
                "explanation", "evidence", "debrief_summary", "debrief_limitations",
                "hints", "provenance", "topics", "quantities", "glossary", "meanings",
                "cases", "learning_path", "conceptual_questions", "options", "blocks",
                "block_labels", "remember", "experimental_question", "prediction_guidance",
            }:
                yield from visible_strings(item)


def test_content_has_complete_progressive_topics_and_unique_ordered_ids():
    assert tuple(item.topic_id for item in content.TOPICS) == (
        "before-starting", "synchronous-generator", "smib", "quantities", "rotor-angle",
        "power-angle", "swing-equation", "fault-stages", "first-swing", "clearing-time",
        "inertia", "time-step", "reading-plots", "limitations",
    )
    assert all(item.title and item.learning_objective.strip() and item.blocks for item in content.TOPICS)
    for items, key in (
        (content.TOPICS, "topic_id"), (content.QUANTITIES, "key"),
        (content.GLOSSARY, "key"), (content.MEANINGS, "key"),
        (content.CASE_GUIDANCE, "case_id"), (content.BLOCK_LABELS, "key"),
    ):
        assert len({getattr(item, key) for item in items}) == len(items)


def test_learning_path_resolves_topics_and_existing_cases_without_solutions():
    assert content.LEARNING_PATH[0].destination == "learn"
    assert content.LEARNING_PATH[0].target_id == "before-starting"
    assert tuple(step.target_id for step in content.LEARNING_PATH[1:]) == LEARNING_ORDER
    assert tuple(item.case_id for item in content.CASE_GUIDANCE) == LEARNING_ORDER
    topics = {item.topic_id for item in content.TOPICS}
    for item in content.CASE_GUIDANCE:
        assert set(item.topic_ids) <= topics
        assert item.observe and item.intervene and item.compare and item.explain
        assert item.case_id in {case.case_id for case in default_guided_cases()}
    serialized = portable.dumps_portable(portable.get_learning_content())
    assert "correct_option_id" not in serialized
    assert "pedagogical_solution" not in serialized
    assert "baseline_config" not in serialized


@pytest.mark.parametrize("key,unit,level", [
    ("H_s", "s", "basic"), ("D_pu", "pu/pu", "advanced"),
    ("f_base_hz", "Hz", "advanced"), ("Pm_pu", "pu", "basic"),
    ("delta_rad", "rad", "basic"), ("omega_dev_pu", "pu", "basic"),
    ("Pmax_prefault_pu", "pu", "basic"), ("Pmax_fault_pu", "pu", "basic"),
    ("Pmax_postfault_pu", "pu", "basic"), ("dt_s", "s", "advanced"),
    ("time_tolerance_s", "s", "advanced"), ("t_clear_s", "s", "basic"),
])
def test_quantity_mapping_retains_units_and_explicit_disclosure(key, unit, level):
    item = content.quantity(key)
    assert (item.unit, item.disclosure) == (unit, level)
    assert item.label and item.symbol and item.description
    assert key not in item.label


def test_configuration_quantities_are_complete_and_do_not_guess_unknown_units():
    configuration = portable.get_guided_case(LEARNING_ORDER[0]).baseline_config
    keys = set()
    for field in fields(configuration):
        value = getattr(configuration, field.name)
        keys.update(item.name for item in fields(value)) if hasattr(value, "__dataclass_fields__") else keys.add(field.name)
    assert keys <= {item.key for item in content.QUANTITIES}
    with pytest.raises(StopIteration):
        content.quantity("unknown_quantity")


def test_glossary_covers_the_variables_and_events_used_by_the_product():
    assert {item.key for item in content.GLOSSARY} >= {
        "pu", "delta", "omega", "inertia", "mechanical-power", "electrical-power",
        "transfer", "fault", "clearing", "first-swing", "cct",
    }
    assert all(item.label and item.description for item in content.GLOSSARY)


def test_theory_reconciles_velocity_damping_domains_and_search_tolerance():
    topics = {item.topic_id: " ".join(block.text for block in item.blocks) for item in content.TOPICS}
    assert "dδ/dt = ωs · Δω" in topics["swing-equation"]
    assert "(Pm − Pe − D · Δω) / (2H)" in topics["swing-equation"]
    assert "pu de potencia por pu de desviación de velocidad" in topics["swing-equation"]
    assert "0 < Pm < Pmax posfalla" in topics["power-angle"]
    assert "|Pm / Pmax prefalla| ≤ 1" in topics["power-angle"]
    assert "no se adivina su orden continuo" in topics["first-swing"]
    assert "no demuestra estabilidad global" in topics["first-swing"]
    assert "No es incertidumbre física" in topics["clearing-time"]
    assert "no demuestra convergencia" in topics["clearing-time"]
    assert "tienen amortiguamiento" in topics["clearing-time"]


def test_portable_content_is_deterministic_immutable_and_exact_across_surfaces():
    dto = portable.get_learning_content()
    encoded = portable.dumps_portable(dto)
    assert encoded == portable.dumps_portable(portable.get_learning_content())
    assert json.loads(encoded) == dto.to_dict() == dispatch("learning_content")
    assert DesktopController().content == dto.to_dict()
    assert dto.topics is content.TOPICS
    with pytest.raises(FrozenInstanceError):
        dto.topics[0].title = "Changed"
    detached = dto.to_dict()
    detached["topics"][0]["blocks"][0]["text"] = "Changed"
    detached["topics"][0]["blocks"].clear()
    assert dto.topics[0].blocks[0].text != "Changed"
    with pytest.raises(FrozenInstanceError):
        dto.topics[0].blocks[0].text = "Changed"


def test_presentation_order_preserves_original_catalog_and_free_baseline():
    assert tuple(case.case_id for case in portable.list_guided_cases()) == (
        "late-clearing-bracket", "controlled-inertia-effect", "first-swing-event-evidence",
    )
    controller = DesktopController()
    assert tuple(item.case_id for item in controller.catalog) == LEARNING_ORDER
    controller.free_fields()
    assert controller.free_config == portable.get_guided_case("late-clearing-bracket").baseline_config
    for case in default_guided_cases():
        view = controller.select_case(case.case_id)
        assert view.prediction_options == case.prediction_options
        assert tuple(key for key, label, description in view.prediction_labels) == case.prediction_options
        assert all(label and description for key, label, description in view.prediction_labels)
        assert tuple(item.key for item in view.fields) == tuple(item.key for item in case.editable_parameters)
    inertia = portable.get_guided_case("controlled-inertia-effect")
    assert tuple(item.key for item in inertia.editable_parameters) == ("H_s",)


def test_reading_content_never_executes_or_reveals_an_attempt(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Content query executed a scientific or solution operation")
    for name in ("run_guided_attempt", "evaluate_transient", "get_guided_solution"):
        monkeypatch.setattr(portable, name, forbidden)
    assert dispatch("learning_content")["topics"]
    controller = DesktopController()
    controller.select_case(LEARNING_ORDER[0])
    assert controller.result is controller.solution is None
    assert controller.history == []
    with pytest.raises(ValueError):
        controller.prepare(None)


def test_primary_static_content_contains_no_roadmap_or_raw_scientific_identifiers():
    strings = list(visible_strings(portable.get_learning_content().to_dict()))
    for case in portable.list_guided_cases():
        strings.extend(visible_strings(portable.get_guided_case(case.case_id).to_dict()))
        strings.extend(portable.get_guided_hints(case.case_id, 2).hints)
        strings.extend(visible_strings(portable.get_guided_solution(case.case_id).to_dict()))
    assert len(strings) > 150
    for text in strings:
        assert not RAW_TERMS.search(text), text
    assert content.meaning("indeterminate").label == "No concluyente"


@pytest.mark.parametrize("case_id", LEARNING_ORDER)
def test_dynamic_interpretations_remain_shared_spanish_and_evidence_backed(case_id):
    source = portable.get_guided_case(case_id)
    result = portable.run_guided_attempt(portable.GuidedAttemptRequest(case_id, source.prediction_options[0]))
    strings = list(visible_strings(result.to_dict()))
    for evaluation in (result.baseline_evaluation, result.attempted_evaluation):
        strings.extend(visible_strings(evaluation.explanation.to_dict()))
        assert evaluation.first_swing.status in {"stable", "unstable", "indeterminate"}
    if result.critical_clearing_explanation:
        strings.extend(visible_strings(result.critical_clearing_explanation.to_dict()))
    assert all(not RAW_TERMS.search(text) for text in strings)
    assert result.local_assessment.pre_score is None
    assert "Diagnóstico inicial:" in result.debrief_summary
    assert "Sin cambios de parámetros" in result.debrief_summary


def test_controlled_intervention_debrief_reports_actual_change_and_retains_caveat():
    result = portable.run_guided_attempt(portable.GuidedAttemptRequest(
        "controlled-inertia-effect", "smaller excursion",
        changes=(portable.ParameterValueDTO("H_s", 6.0),),
    ))
    assert "3.5 → 6 s" in result.debrief_summary
    comparison = result.scientific_comparison
    assert format(comparison.attempted_max_delta_rad, ".6g") in result.debrief_summary
    assert format(comparison.baseline_max_abs_omega_dev_pu, ".6g") in result.debrief_summary
    assert "no implica" in " ".join(result.debrief_limitations)
    assert "una mayor inercia siempre" in " ".join(result.debrief_limitations)


def test_indeterminate_presentation_keeps_reason_and_advanced_evidence():
    controller = DesktopController()
    source = portable.get_guided_case(LEARNING_ORDER[0]).baseline_config
    result = portable.evaluate_transient(replace(source, t_end_s=0.21))
    controller.accept_free(result)
    view = controller.free_result_view()
    assert view.status == "indeterminate"
    assert view.status_label == "No concluyente"
    assert view.reason == "horizon_ended_before_event"
    assert result.explanation.summary in view.explanation
    assert "horizon_ended_before_event" in view.advanced
    assert not RAW_TERMS.search(view.explanation)


def test_scientific_content_has_one_owner_and_renderers_do_not_copy_theory():
    tree = ast.parse((ROOT / "src/sincrolab/application/learning_content.py").read_text(encoding="utf-8"))
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {"dataclasses"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    renderers = "\n".join(path.read_text(encoding="utf-8") for folder, pattern in (
        (ROOT / "web", "*.js"), (ROOT / "src/sincrolab/interfaces/desktop", "*.py"),
    ) for path in folder.glob(pattern))
    for topic in content.TOPICS:
        for block in topic.blocks:
            assert block.text not in renderers
    for case in content.CASE_GUIDANCE:
        for key in ("remember", "observe", "experimental_question", "prediction_guidance"):
            assert getattr(case, key) not in renderers
    for quantity in content.QUANTITIES:
        assert quantity.description not in renderers
    assert 'runtime.call("learning_content")' in renderers
    assert 'portable.get_learning_content()' in renderers


@pytest.mark.parametrize("topic", content.TOPICS, ids=lambda topic: topic.topic_id)
def test_lesson_units_prepare_equations_and_lead_to_reflection_and_experiment(topic):
    kinds = [block.kind for block in topic.blocks]
    assert kinds[0] == "intuition"
    assert {"explanation", "example", "reflection", "experiment"} <= set(kinds)
    assert kinds.index("reflection") < kinds.index("experiment")
    assert kinds[-1] == "experiment"
    if "equation" in kinds:
        assert kinds.index("explanation") < kinds.index("equation") < kinds.index("example")
    assert all(block.text.strip() for block in topic.blocks)
    assert set(kinds) <= {label.key for label in content.BLOCK_LABELS}
    assert topic.case_ids


def test_prerequisites_are_earlier_lessons_and_all_experiment_links_resolve():
    order = {topic.topic_id: i for i, topic in enumerate(content.TOPICS)}
    cases = {case.case_id for case in default_guided_cases()}
    for topic in content.TOPICS:
        assert len(set(topic.prerequisite_topic_ids)) == len(topic.prerequisite_topic_ids)
        assert all(order[key] < order[topic.topic_id] for key in topic.prerequisite_topic_ids)
        assert set(topic.case_ids) <= cases
        assert len(set(topic.case_ids)) == len(topic.case_ids)
    for guidance in content.CASE_GUIDANCE:
        assert guidance.remember and guidance.experimental_question and guidance.prediction_guidance
        assert guidance.experimental_question.endswith("?")
    prerequisites = {case.case_id: set(case.topic_ids) for case in content.CASE_GUIDANCE}
    assert {"rotor-angle", "fault-stages", "first-swing", "reading-plots"} <= prerequisites[LEARNING_ORDER[0]]
    assert {"fault-stages", "clearing-time"} <= prerequisites[LEARNING_ORDER[1]]
    assert {"swing-equation", "inertia"} <= prerequisites[LEARNING_ORDER[2]]


@pytest.mark.parametrize("kind,text", [("answer", "x"), ("equation", ""), ("reflection", "  ")])
def test_learning_blocks_reject_missing_text_and_non_content_semantics(kind, text):
    with pytest.raises(ValueError):
        content.LearningBlock(kind, text)


def test_prerequisite_and_causal_wording_addresses_novice_misconceptions():
    topics = {item.topic_id: " ".join(block.text for block in item.blocks) for item in content.TOPICS}
    assert all(term in topics["synchronous-generator"] for term in ("rotor", "estator", "campo magnético", "pares de polos", "frecuencia"))
    assert "La red no gira como un objeto sólido" in topics["smib"]
    assert "Δω = 0 no significa rotor detenido" in topics["rotor-angle"]
    assert "dδ/dt = ωs · Δω" in topics["rotor-angle"]
    assert "70 MW" in topics["quantities"] and "100 MVA" in topics["quantities"]
    assert "δ y Δω permanecen continuos" in topics["fault-stages"]
    assert "balance neto instantáneo" in topics["inertia"]
    assert "no garantiza siempre estabilidad" in topics["inertia"]
    assert "Paso temporal (dt_s) ≠ tolerancia de búsqueda (time_tolerance_s)" in topics["time-step"]
    assert "sin interpolación" in topics["first-swing"]
    assert "positiva en ambas muestras" in topics["first-swing"]
    assert "ausencia de amortiguamiento" in topics["clearing-time"]


def test_learning_content_and_preparation_have_no_answer_or_solution_payloads():
    forbidden = {
        "correct_option_id", "answers", "correct_answers", "settings", "expected_outcome",
        "expected_status", "baseline_evaluation", "attempted_evaluation", "pedagogical_solution",
        "target_status", "solution", "score", "baseline_config",
    }
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
    inspect(portable.get_learning_content().to_dict())
    for case in content.CASE_GUIDANCE:
        preparation = " ".join(getattr(case, key) for key in (
            "remember", "observe", "experimental_question", "prediction_guidance",
        ))
        # Preparation gives concepts, not parameter prescriptions or forecasted outcomes.
        assert not re.search(r"[0-9]|este caso será|la respuesta es|una solución", preparation, re.I)
    assert {field.name for field in fields(content.LearningBlock)} == {"kind", "text"}


def test_numerical_examples_agree_with_the_existing_physical_owner():
    from math import pi
    import numpy as np
    from sincrolab.models import SMIBParameters
    from sincrolab.models.power_angle import electrical_power_pu, initial_equilibrium_angle_rad
    from sincrolab.models.swing import smib_swing_rhs

    angle = initial_equilibrium_angle_rad(0.5, 1.0)
    assert angle == pytest.approx(pi / 6)
    assert electrical_power_pu(angle, 1.0) == pytest.approx(0.5)
    assert electrical_power_pu(angle, 0.4) == pytest.approx(0.2)
    parameters = SMIBParameters(H_s=4.0, D_pu=0.0, f_base_hz=50.0, Pm_pu=0.7)
    derivative = smib_swing_rhs(0.0, np.array([angle, 0.0]), parameters, Pmax_pu=1.0)
    assert derivative == pytest.approx([0.0, 0.025])
    rotating = smib_swing_rhs(0.0, np.array([angle, 0.01]), parameters, Pmax_pu=1.0)
    assert rotating[0] == pytest.approx(pi)
    for inertia, expected in ((4.0, 0.02), (8.0, 0.01)):
        parameters = replace(parameters, H_s=inertia, Pm_pu=0.16)
        derivative = smib_swing_rhs(0.0, np.zeros(2), parameters, Pmax_pu=0.0)
        assert derivative[1] == pytest.approx(expected)
