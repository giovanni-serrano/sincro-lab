"""Functional shared-content rendering through the optional Qt surface."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QCheckBox

from sincrolab.application import portable
from sincrolab.interfaces.desktop.window import MainWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    widget = MainWindow()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_home_path_and_direct_navigation_share_portable_content(window):
    assert window.navigation_buttons["learn"].text() == "Aprender"
    assert len(window.home.cards) == len(portable.get_learning_content().cases)
    assert window.home.learn_button.width() > 60
    assert window.home.browse_button.width() > 100
    assert window.home.free_button.width() > 60
    window.home.learn_button.click()
    assert window.stack.currentWidget() is window.learn
    assert window.controller.result is None
    window.navigate("free")
    assert window.stack.currentWidget() is window.free


@pytest.mark.parametrize("topic_id", [topic.topic_id for topic in portable.get_learning_content().topics])
def test_learn_navigation_renders_exact_shared_topic(window, topic_id):
    window.resize(820, 620)
    window.open_topic(topic_id)
    QApplication.processEvents()
    topic = next(item for item in portable.get_learning_content().topics if item.topic_id == topic_id)
    assert window.learn.topic_title.text() == topic.title
    assert window.learn.objective.text() == topic.learning_objective
    assert [text.text() for heading, text in window.learn.block_widgets] == [block.text for block in topic.blocks]
    assert [text.property("block_kind") for heading, text in window.learn.block_widgets] == [block.kind for block in topic.blocks]
    labels = {item.key: item.label for item in portable.get_learning_content().block_labels}
    assert [heading.text() for heading, text in window.learn.block_widgets] == [labels[block.kind] for block in topic.blocks]
    assert window.learn.horizontalScrollBar().maximum() == 0


def test_glossary_uses_shared_definitions_and_does_not_discard_prediction(window):
    window.open_case("first-swing-event-evidence")
    window.detail.begin_button.click()
    window.detail.prediction.setCurrentIndex(1)
    prediction = window.controller.prediction
    window.open_topic("glossary")
    for item in portable.get_learning_content().glossary:
        assert item.label in window.learn.topic_text.text()
        assert item.description in window.learn.topic_text.text()
    window.open_case("first-swing-event-evidence")
    assert window.controller.prediction == prediction
    assert window.controller.result is None


def test_primary_predictions_and_parameters_use_labels_with_technical_details_opt_in(window):
    window.open_case("controlled-inertia-effect")
    case = window.controller.case_view()
    assert "H_s" not in " ".join(row[0] for row in case.configuration)
    assert not window.detail.advanced_baseline.isVisible()
    toggle = window.detail.findChild(QCheckBox, "toggle_baseline_advanced")
    toggle.click()
    assert window.detail.advanced_baseline.isVisible()
    assert any("H_s" in row[0] for row in case.advanced_configuration)
    window.detail.begin_button.click()
    for index, (key, label, description) in enumerate(case.prediction_labels, start=1):
        assert window.detail.prediction.itemData(index) == key
        assert window.detail.prediction.itemText(index) == label
        assert description in window.detail.prediction_help.text()
    assert "H_s" not in window.detail.pending_changes.text()


def test_completed_prediction_is_translated_but_retained_value_is_unchanged(window):
    controller = window.controller
    controller.select_case("first-swing-event-evidence")
    controller.prepare("stable")
    controller.accept_guided(controller.guided_job()())
    window.open_case(controller.case.case_id)
    assert controller.result.prediction == "stable"
    assert window.detail.result_panel.prediction.text() == "Predicción registrada: Estable"


@pytest.mark.parametrize("guidance", portable.get_learning_content().cases, ids=lambda item: item.case_id)
def test_preparation_and_review_links_work_before_any_prediction_or_execution(window, guidance):
    window.open_case(guidance.case_id)
    for preparation in (window.detail.observe_preparation, window.detail.predict_preparation):
        assert {key: control.text() for key, control in preparation.texts.items()} == {
            key: getattr(guidance, key) for key in preparation.texts
        }
        assert tuple(preparation.topic_buttons) == guidance.topic_ids
    window.detail.begin_button.click()
    assert window.detail.predict_preparation.isVisible()
    assert not window.detail.run_button.isEnabled()
    for key in guidance.topic_ids:
        window.detail.predict_preparation.topic_buttons[key].click()
        assert window.stack.currentWidget() is window.learn
        assert window.learn.topics.currentData() == key
        window.learn.return_button.click()
        assert window.stack.currentWidget() is window.detail
        assert window.controller.phase == "Predecir"
    assert window.controller.result is window.controller.solution is None
    assert window.controller.prediction is None and window.controller.history == []


def test_theory_next_prerequisite_and_experiment_links_preserve_active_attempt(window):
    topics = portable.get_learning_content().topics
    window.open_topic(topics[0].topic_id)
    for topic in topics[1:]:
        window.learn.next_button.click()
        assert window.learn.topics.currentData() == topic.topic_id
    assert window.learn.next_button is None
    for topic in topics:
        for prerequisite in topic.prerequisite_topic_ids:
            window.open_topic(topic.topic_id)
            window.learn.topic_buttons[prerequisite].click()
            assert window.learn.topics.currentData() == prerequisite
        for case_id in topic.case_ids:
            window.open_topic(topic.topic_id)
            window.learn.case_buttons[case_id].click()
            assert window.controller.case.case_id == case_id
            assert window.controller.result is None
    window.open_case("controlled-inertia-effect")
    window.detail.begin_button.click()
    window.detail.prediction.setCurrentIndex(1)
    prediction = window.controller.prediction
    window.open_topic("inertia")
    window.learn.case_buttons["controlled-inertia-effect"].click()
    assert window.controller.prediction == prediction
    assert window.controller.result is None
