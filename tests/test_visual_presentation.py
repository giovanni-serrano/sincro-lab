"""Shared visual contracts and native interaction; no cosmetic pixel oracle."""

import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from sincrolab.application import portable


ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "src/sincrolab/interfaces/assets"


def test_shared_topic_groups_preserve_all_canonical_topics_in_order():
    design = json.loads((ASSETS / "design.json").read_text(encoding="utf-8"))
    topics = portable.get_learning_content().topics
    indices = [index for group in design["topic_groups"]
               for index in range(group["start"], group["stop"])]
    assert indices == list(range(len(topics)))
    known = {topic.topic_id for topic in topics}
    for diagram in design["diagrams"].values():
        assert set(diagram["topics"]) <= known


@pytest.mark.parametrize("name", ["smib.svg", "rotor-angle.svg", "timeline.svg", "causal-chain.svg"])
def test_conceptual_svg_is_scalable_named_and_contains_no_external_or_runtime_content(name):
    svg = ET.parse(ASSETS / name).getroot()
    namespace = "{http://www.w3.org/2000/svg}"
    assert svg.attrib["viewBox"].startswith("0 0 ")
    assert svg.find(f"{namespace}title").text
    assert svg.find(f"{namespace}desc").text
    for node in svg.iter():
        assert node.tag not in {f"{namespace}{tag}" for tag in ("script", "image", "foreignObject", "animate", "set")}
        assert not any(key.startswith("on") or "href" in key for key in node.attrib)
    assert "stable" not in "".join(svg.itertext()).lower()


def test_desktop_event_markers_retain_owner_times_and_original_sample_objects():
    from sincrolab.interfaces.desktop.adapter import DesktopController
    controller = DesktopController()
    controller.select_case("late-clearing-bracket")
    controller.prepare(controller.case.prediction_options[0])
    controller.accept_guided(controller.guided_job()())
    result = controller.result
    curve = controller.result_view().curves[1]
    assert curve.time_s is result.attempted_evaluation.trajectory.time_s
    assert curve.delta_rad is result.attempted_evaluation.trajectory.delta_rad
    assert curve.omega_dev_pu is result.attempted_evaluation.trajectory.omega_dev_pu
    assert [time for label, time in curve.events] == [result.attempted_config.network.t_fault_s,
                                                     result.attempted_config.network.t_clear_s]


@pytest.fixture
def window():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from sincrolab.interfaces.desktop.window import MainWindow
    app = QApplication.instance() or QApplication([])
    value = MainWindow()
    value.show()
    app.processEvents()
    yield value
    value.close()
    value.deleteLater()
    app.processEvents()


def test_radio_rows_use_canonical_meanings_and_keyboard_selection(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    window.open_case("first-swing-event-evidence")
    window.detail.begin_button.click()
    assert not window.detail.run_button.isEnabled()
    assert len(window.detail.prediction.rows) == len(window.controller.case.prediction_options)
    radio = window.detail.prediction.rows[0][1]
    window.detail.ensureWidgetVisible(radio)
    QApplication.processEvents()
    radio.setFocus()
    QTest.keyClick(radio, Qt.Key.Key_Space)
    assert window.controller.prediction == window.controller.case.prediction_options[0]
    assert window.detail.run_button.isEnabled()
    QTest.keyClick(radio, Qt.Key.Key_Down)
    assert window.controller.prediction == window.controller.case.prediction_options[1]
    assert sum(control.isChecked() for row, control in window.detail.prediction.rows) == 1
    assert window.controller.result is None


def test_phase_states_distinguish_unvisited_available_from_completed(window):
    window.open_case("controlled-inertia-effect")
    view = window.detail
    assert view.steps["Simular"].property("phase_state") == "Bloqueada"
    view.begin_button.click()
    assert view.steps["Observar"].property("phase_state") == "Completada"
    assert "Actual" in view.steps["Predecir"].accessibleName()
    controller = window.controller
    controller.prepare(controller.case.prediction_options[0])
    controller.accept_guided(controller.guided_job()())
    window._render_guided()
    view.steps["Explicar"].click()
    assert view.steps["Intervenir"].property("phase_state") == "Disponible"
    assert view.steps["Comparar"].property("phase_state") == "Disponible"
    assert view.steps["Simular"].property("phase_state") == "Completada"


def test_theory_previous_and_case_return_preserve_pending_prediction(window):
    window.open_case("first-swing-event-evidence")
    window.detail.begin_button.click()
    window.detail.prediction.setCurrentIndex(1)
    prediction = window.controller.prediction
    window.open_topic("rotor-angle")
    assert "Caso 1" in window.learn.return_button.text()
    assert "Predecir" in window.learn.return_button.text()
    window.learn.previous_button.click()
    assert window.learn.topics.currentData() == "quantities"
    window.learn.return_button.click()
    assert window.controller.prediction == prediction
    assert window.controller.result is None


def test_diagrams_preserve_aspect_ratio_when_height_is_capped(window):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from sincrolab.interfaces.desktop.assets import Diagram
    window.resize(1280, 820)
    QApplication.processEvents()
    for diagram in window.home.findChildren(Diagram):
        assert diagram.svg.renderer().aspectRatioMode() == Qt.AspectRatioMode.KeepAspectRatio
        assert diagram.svg.height() <= 280


def test_qt_and_web_read_identical_svg_bytes(window):
    from sincrolab.interfaces.desktop.assets import asset_bytes
    for path in ASSETS.glob("*.svg"):
        assert hashlib.sha256(asset_bytes(path.name)).digest() == hashlib.sha256(path.read_bytes()).digest()
