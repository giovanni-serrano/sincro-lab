"""Qt interaction tests using controlled doubles plus real portable runs."""

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QElapsedTimer, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from sincrolab.application import portable
from sincrolab.interfaces.desktop.adapter import DesktopController
from sincrolab.interfaces.desktop.window import MainWindow


@pytest.fixture(scope="module")
def app():
    value = QApplication.instance() or QApplication([])
    value.setStyle("Fusion")
    return value


def wait_for(window, app):
    timer = QElapsedTimer()
    timer.start()
    while window.worker is not None and timer.elapsed() < 15000:
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    assert window.worker is None, "Worker failed to deliver its terminal signal"
    app.processEvents()


@pytest.fixture
def window(app):
    value = MainWindow()
    value.show()
    app.processEvents()
    yield value
    wait_for(value, app)
    value.close()
    value.deleteLater()
    app.processEvents()


def predict_and_run(window, app, option=1):
    window.detail.prediction.setCurrentIndex(option)
    window.detail.run_button.click()
    assert not window.sidebar.isEnabled()
    wait_for(window, app)
    assert window.last_error is None


@pytest.mark.parametrize("case_id", [
    "late-clearing-bracket", "controlled-inertia-effect", "first-swing-event-evidence",
])
def test_real_six_phase_workflow_and_solution(window, app, case_id):
    window.open_case(case_id)
    view = window.detail
    assert window.controller.phase == "Observar"
    assert window.controller.result is None
    assert view.solution.text() == ""
    assert not view.result_panel.isVisible()
    assert not view.steps["Comparar"].isEnabled()
    view.begin_button.click()
    assert view.panels["Predecir"].isVisible()
    assert not view.run_button.isEnabled()
    assert view.prediction.currentData() is None
    assert [view.prediction.itemData(i) for i in range(1, view.prediction.count())] == list(
        portable.get_guided_case(case_id).prediction_options
    )
    predict_and_run(window, app)
    first = window.controller.result
    assert view.result_panel.status.text() == first.attempted_evaluation.first_swing.status.upper()
    view.intervene_button.click()
    assert view.panels["Intervenir"].isVisible()
    assert tuple(view.editor.inputs) == tuple(
        item.key for item in portable.get_guided_case(case_id).editable_parameters
    )
    view.hint_button.click()
    assert window.controller.hints == portable.get_guided_hints(case_id, 1).hints
    assert not window.controller.solution
    view.hint_button.click()
    assert not view.hint_button.isEnabled()
    view.solution_button.click()
    assert view.panels["Predecir"].isVisible()
    assert not view.run_button.isEnabled()
    assert "Una solución pedagógica posible" in view.prediction_solution.text()
    predict_and_run(window, app)
    result = window.controller.result
    assert result.goal_evaluation.achieved
    assert view.panels["Comparar"].isVisible()
    assert view.history.rowCount() == 2
    assert view.changed_parameters.item(0, 0).text() == result.changed_parameters[0].key
    assert view.compare_plot.curves[0].delta_rad is result.baseline_evaluation.trajectory.delta_rad
    view.explain_button.click()
    assert view.panels["Explicar"].isVisible()
    assert result.attempted_evaluation.explanation.summary in view.explanation.toPlainText()
    assert result.debrief_summary in view.debrief.text()
    assert not view.assess_button.isVisible()
    assert "no realizada" in view.score.text()


def test_ui_unanswered_assessment_is_not_scored_and_completed_pair_uses_h25(window, app):
    window.open_case("controlled-inertia-effect")
    view = window.detail
    view.begin_button.click()
    view.prediction.setCurrentIndex(3)
    view.assess_enabled.setChecked(True)
    view.run_button.click()
    assert window.worker is None
    assert window.controller.result is None
    assert window.last_error is not None
    assert "Completa" in view.error.text()
    for control in view.pre_questions.inputs.values():
        control.setCurrentIndex(2)
    predict_and_run(window, app, 3)
    assert not window.controller.result.local_assessment.assessed
    view.steps["Explicar"].click()
    view.assess_button.click()
    assert window.worker is None
    assert not window.controller.result.local_assessment.assessed
    view.post_questions.inputs["accelerating_power"].setCurrentIndex(1)
    view.post_questions.inputs["first_swing_evidence"].setCurrentIndex(2)
    view.assess_button.click()
    wait_for(window, app)
    assert window.last_error is None
    assert window.controller.result.local_assessment.pre_score.correct == 1
    assert window.controller.result.local_assessment.post_score.correct == 2
    assert len(window.controller.history) == 1
    assert "Post: 2/2" in view.score.text()


def test_back_forward_and_case_switch_do_not_leak_active_state(window, app):
    window.open_case("controlled-inertia-effect")
    window.detail.begin_button.click()
    predict_and_run(window, app)
    result = window.controller.result
    window.detail.back_button.click()
    window.open_case("controlled-inertia-effect")
    assert window.controller.result is result
    window.open_case("first-swing-event-evidence")
    assert window.controller.result is None
    assert window.detail.stage.text().endswith("Observar")
    assert window.detail.prediction.currentData() is None
    assert not window.detail.panels["Explicar"].isVisible()
    assert window.controller.history == []
    assert window.detail.result_panel.plot.curves == ()
    assert window.detail.result_panel.status.text() == ""
    assert window.detail.explanation.toPlainText() == ""
    assert window.detail.history.rowCount() == 0


def test_hints_do_not_discard_unsubmitted_editor_input(window, app):
    window.open_case("controlled-inertia-effect")
    window.detail.begin_button.click()
    predict_and_run(window, app)
    window.detail.intervene_button.click()
    editor = window.detail.editor.inputs["H_s"]
    editor.setText("5.75")
    window.detail.hint_button.click()
    assert editor.text() == "5.75"
    window.detail.apply_button.click()
    assert window.controller.changes == {"H_s": 5.75}
    assert window.controller.prediction is None


def test_free_mode_handles_invalid_input_and_real_indeterminate(window, app):
    window.navigate("free")
    fields = window.free.editor.inputs
    fields["H_s"].setText("not a number")
    window.free.run_button.click()
    assert window.worker is None
    assert window.last_error is not None
    assert window.controller.free_result is None
    fields["H_s"].setText("3.5")
    fields["t_clear_s"].setText("0.2")
    fields["t_end_s"].setText("0.21")
    window.free.run_button.click()
    wait_for(window, app)
    assert window.last_error is None
    assert window.free.result_panel.status.text() == "INDETERMINATE"
    assert window.controller.free_result.first_swing.status == "indeterminate"
    retained = window.controller.free_result
    fields["dt_s"].setText("-1")
    window.free.run_button.click()
    wait_for(window, app)
    assert isinstance(window.last_error, ValueError)
    assert window.controller.free_result is retained
    assert window.free.result_panel.status.text() == "INDETERMINATE"
    assert "Traceback" not in window.free.error.text()


@pytest.mark.parametrize("status", ["stable", "unstable", "indeterminate"])
def test_ui_double_preserves_returned_status_without_classification(app, status):
    source = portable.run_guided_attempt(
        portable.GuidedAttemptRequest("first-swing-event-evidence", "stable")
    )
    # A display double exercises rendering, not scientific parity.
    evaluation = replace(source.attempted_evaluation,
                         first_swing=replace(source.attempted_evaluation.first_swing, status=status))
    returned = replace(source, attempted_evaluation=evaluation)
    class StubController(DesktopController):
        def guided_job(self):
            return lambda: returned
    controller = StubController()
    widget = MainWindow(controller)
    widget.show()
    widget.open_case(source.case_id)
    widget.detail.begin_button.click()
    predict_and_run(widget, app)
    assert widget.detail.result_panel.status.text() == status.upper()
    assert widget.controller.result is returned
    widget.close()
    widget.deleteLater()


def test_worker_failure_retains_exception_and_keeps_navigation_usable(app):
    failure = RuntimeError("Synthetic invariant failure for presentation test")
    class FailingController(DesktopController):
        def guided_job(self):
            def fail():
                raise failure
            return fail
    widget = MainWindow(FailingController())
    widget.show()
    widget.open_case("controlled-inertia-effect")
    widget.detail.begin_button.click()
    widget.detail.prediction.setCurrentIndex(1)
    widget.detail.run_button.click()
    wait_for(widget, app)
    assert widget.last_error is failure
    assert widget.controller.result is None
    assert widget.sidebar.isEnabled()
    assert widget.detail.error.isVisible()
    assert "Traceback" not in widget.detail.error.text()
    widget.navigate("home")
    assert widget.stack.currentWidget() is widget.home
    widget.close()
    widget.deleteLater()


@pytest.mark.parametrize("phase", ["Observar", "Predecir", "Simular", "Intervenir", "Comparar", "Explicar"])
def test_all_phases_fit_minimum_width_and_allow_vertical_scroll(window, app, phase):
    window.resize(820, 620)
    window.open_case("controlled-inertia-effect")
    window.detail.begin_button.click()
    predict_and_run(window, app)
    window.detail.steps[phase].click()
    app.processEvents()
    page = window.detail
    assert page.horizontalScrollBar().maximum() == 0
    assert page.widget().width() <= page.viewport().width()
    assert page.panels[phase].isVisible()
