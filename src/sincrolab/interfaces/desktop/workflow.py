"""Educational views emitting intents; no application imports or scoring."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QCheckBox, QComboBox, QFormLayout, QGridLayout, QHeaderView,
    QHBoxLayout, QLineEdit, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QSizePolicy,
)

from sincrolab.interfaces.desktop.plots import TrajectoryPlot
from sincrolab.interfaces.desktop.presentation import (
    CaseView, InputField, PHASES, QuestionView, ResultView, number,
)
from sincrolab.interfaces.desktop.views import Page
from sincrolab.interfaces.desktop.widgets import PredictionChoices, button, label
from sincrolab.interfaces.desktop.assets import Diagram


def table(headers: tuple[str, ...], name: str) -> QTableWidget:
    view = QTableWidget(0, len(headers))
    view.setObjectName(name)
    view.setHorizontalHeaderLabels(headers)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    view.verticalHeader().hide()
    view.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    view.setWordWrap(True)
    view.setMinimumHeight(130)
    return view


def fill_table(view: QTableWidget, rows: tuple[tuple[str, ...], ...]) -> None:
    view.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            view.setItem(row, column, QTableWidgetItem(value))
    view.resizeRowsToContents()
    height = view.horizontalHeader().height() + sum(
        view.rowHeight(row) for row in range(view.rowCount())
    ) + 6
    view.setFixedHeight(min(390, max(90, height)))


def disclosure(title: str, content: QWidget) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    control = QCheckBox(title)
    control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    control.setObjectName(f"toggle_{content.objectName()}")
    control.toggled.connect(content.setVisible)
    content.hide()
    layout.addWidget(control)
    layout.addWidget(content)
    return panel


def text_panel(name: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setObjectName(name)
    widget.setReadOnly(True)
    widget.setMinimumHeight(240)
    return widget


class ParameterEditor(QWidget):
    def __init__(self, fields: tuple[InputField, ...], parent=None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.inputs = {}
        for item in fields:
            control = QLineEdit(number(item.value))
            control.setObjectName(f"input_{item.key}")
            control.setAccessibleName(item.label)
            bound = "" if item.minimum is None else (
                f" · [{number(item.minimum)}, {number(item.maximum)}]"
            )
            caption = label(f"{item.label}{bound}\n{item.description}")
            caption.setBuddy(control)
            layout.addRow(caption, control)
            self.inputs[item.key] = control

    def values(self) -> dict[str, str]:
        return {key: item.text() for key, item in self.inputs.items()}

    def set_values(self, fields: tuple[InputField, ...]) -> None:
        for item in fields:
            self.inputs[item.key].setText(number(item.value))


class QuestionEditor(QWidget):
    def __init__(self, questions: tuple[QuestionView, ...], prefix: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.inputs = {}
        for question in questions:
            layout.addWidget(label(question.prompt))
            control = QComboBox()
            control.setObjectName(f"{prefix}_{question.key}")
            control.setAccessibleName(question.prompt)
            control.addItem("Sin responder", None)
            for key, text in question.options:
                control.addItem(text, key)
            control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            control.setMinimumContentsLength(12)
            layout.addWidget(control)
            self.inputs[question.key] = control

    def values(self) -> dict[str, str]:
        return {key: item.currentData() for key, item in self.inputs.items()
                if item.currentData() is not None}


class ResultPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.status = label("", "result_status")
        self.status.setObjectName("observed_status")
        self.reason = label("", "muted")
        self.prediction = label("")
        self.plot = TrajectoryPlot()
        self.configuration = table(("Parámetro", "Valor"), "result_config")
        layout.addWidget(self.status)
        layout.addWidget(self.reason)
        layout.addWidget(self.prediction)
        self.interpretation = label("")
        layout.addWidget(self.plot)
        layout.addWidget(label("Interpretación", "title"))
        layout.addWidget(self.interpretation)
        layout.addWidget(disclosure("Parámetros de esta ejecución", self.configuration))
        self.advanced = text_panel("result_advanced")
        layout.addWidget(disclosure("Detalles avanzados · configuración y evidencia", self.advanced))

    def render(self, result: ResultView) -> None:
        self.status.setText(result.status_label)
        self.status.setProperty("status", result.status)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.reason.setText(result.reason_label)
        self.prediction.setText(f"Predicción registrada: {result.prediction_label}" if result.prediction else "")
        self.interpretation.setText(result.explanation)
        self.advanced.setPlainText(result.advanced)
        self.plot.set_curves(result.curves)
        fill_table(self.configuration, result.configuration)


class CasePreparation(QWidget):
    """Display shared preparation before prediction without collecting answers."""

    learn_requested = Signal(str)

    def __init__(self, parent=None, *, compact=False) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.texts = {}
        self.detail_content = QWidget()
        expanded = QVBoxLayout(self.detail_content)
        expanded.setContentsMargins(0, 0, 0, 0)
        for key, title in (
            ("remember", "Qué debes recordar"), ("observe", "Qué debes observar"),
            ("experimental_question", "Pregunta experimental"),
            ("prediction_guidance", "Antes de predecir"),
        ):
            target = layout if not compact or key == "prediction_guidance" else expanded
            target.addWidget(label(title, "title"))
            self.texts[key] = label("")
            target.addWidget(self.texts[key])
        if compact:
            self.detail_content.setObjectName("prediction_preparation")
            layout.addWidget(disclosure("Recordar el contexto y la pregunta experimental", self.detail_content))
        self.links = QVBoxLayout()
        (expanded if compact else layout).addLayout(self.links)
        self.topic_buttons = {}
        self.current_links = None

    def set_case(self, case: CaseView) -> None:
        guidance = dict(case.guidance)
        for key, control in self.texts.items():
            control.setText(guidance[key])
        if self.current_links == case.topic_links:
            return
        self.current_links = case.topic_links
        while self.links.count():
            widget = self.links.takeAt(0).widget()
            widget.setParent(None)
            widget.deleteLater()
        self.topic_buttons = {}
        for key, title in case.topic_links:
            control = button("Repasar: " + title, f"review_{key}", "link")
            control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            control.setAccessibleName(f"Repasar: {title}")
            control.clicked.connect(lambda checked=False, target=key: self.learn_requested.emit(target))
            self.links.addWidget(control)
            self.topic_buttons[key] = control


class CaseDetailPage(Page):
    back_requested = Signal()
    learn_requested = Signal(str)
    intent = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__("case_detail", parent)
        self.preview = None
        self.back_button = button("Volver a casos guiados", "back_to_cases")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.body.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.concept = label("", "eyebrow")
        self.title = label("", "heading")
        self.difficulty = label("", "badge")
        for item in (self.concept, self.title):
            self.body.addWidget(item)
        self.body.addWidget(self.difficulty, 0, Qt.AlignmentFlag.AlignLeft)
        steps = QHBoxLayout()
        steps.setSpacing(4)
        self.steps = {}
        for index, phase in enumerate(PHASES):
            control = button(f"{index + 1}\n{phase}", f"phase_{phase}", "step")
            control.setCheckable(True)
            control.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            control.clicked.connect(lambda checked=False, p=phase: self.intent.emit("phase", p))
            steps.addWidget(control, 1)
            self.steps[phase] = control
        self.body.addLayout(steps)
        self.error = label("", "error")
        self.error.setObjectName("workflow_error")
        self.error.hide()
        self.body.addWidget(self.error)
        self.stage = label("", "section")
        self.body.addWidget(self.stage)
        self.panels = {}
        for phase in PHASES:
            panel = QWidget()
            panel.setObjectName(f"panel_{phase}")
            self.panels[phase] = panel
            self.body.addWidget(panel)
        self._build_observe()
        self._build_predict()
        self._build_result()
        self._build_intervene()
        self._build_compare()
        self._build_explain()
        self.body.addStretch()

    def resizeEvent(self, event) -> None:
        if hasattr(self, "prediction_columns"):
            wide = self.width() >= 870
            self.prediction_columns.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)
        super().resizeEvent(event)

    def _build_observe(self) -> None:
        layout = QVBoxLayout(self.panels["Observar"])
        self.context = label("")
        self.objective = label("")
        self.baseline = table(("Parámetro", "Inicial"), "baseline_config")
        self.provenance = label("", "muted")
        for item in (label("Objetivo de aprendizaje", "title"), self.objective,
                     self.context, self.provenance):
            layout.addWidget(item)
        layout.addWidget(Diagram("timeline"))
        self.observe_preparation = CasePreparation()
        self.observe_preparation.learn_requested.connect(self.learn_requested.emit)
        layout.addWidget(self.observe_preparation)
        layout.addWidget(disclosure("Parámetros de la configuración inicial", self.baseline))
        self.advanced_baseline = table(("Parámetro e identificador", "Valor"), "baseline_advanced")
        layout.addWidget(disclosure("Detalles avanzados · configuración completa", self.advanced_baseline))
        self.begin_button = button("Registrar mi predicción", "begin_prediction", "primary")
        self.begin_button.clicked.connect(lambda: self.intent.emit("phase", "Predecir"))
        layout.addWidget(self.begin_button)

    def _build_predict(self) -> None:
        self.prediction_columns = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.panels["Predecir"])
        self.prediction_columns.setSpacing(28)
        self.predict_preparation = CasePreparation(compact=True)
        self.predict_preparation.learn_requested.connect(self.learn_requested.emit)
        self.prediction_columns.addWidget(self.predict_preparation, 1, Qt.AlignmentFlag.AlignTop)
        self.prediction_action = QWidget()
        self.predict_layout = QVBoxLayout(self.prediction_action)
        self.predict_layout.setContentsMargins(0, 0, 0, 0)
        self.prediction_columns.addWidget(self.prediction_action, 2, Qt.AlignmentFlag.AlignTop)
        self.prediction_prompt = label("")
        self.prediction_help = label("")
        self.prediction = PredictionChoices()
        self.prediction.setObjectName("prediction")
        self.prediction.setAccessibleName("Predicción del intento")
        self.prediction.currentIndexChanged.connect(self._prediction_changed)
        self.pending_changes = label("", "muted")
        self.prediction_solution = label("")
        self.assess_enabled = QCheckBox("Autoevaluación (opcional)")
        self.assess_enabled.setObjectName("enable_assessment")
        self.pre_holder = QVBoxLayout()
        self.pre_questions = None
        self.assess_enabled.toggled.connect(self._toggle_pre)
        for item in (self.prediction_prompt, self.pending_changes,
                     self.prediction_solution, self.prediction,
                     self.assess_enabled):
            self.predict_layout.addWidget(item)
        self.predict_layout.addLayout(self.pre_holder)
        self.run_button = button("Simular con esta predicción", "run_guided", "primary")
        self.run_button.clicked.connect(lambda: self.intent.emit("run", {
            "prediction": self.prediction.currentData(),
            "pre": self.pre_questions.values() if self.assess_enabled.isChecked() else None,
        }))
        self.predict_layout.addWidget(self.run_button)

    def _prediction_changed(self) -> None:
        self.run_button.setEnabled(self.prediction.currentData() is not None)
        self.intent.emit("prediction", self.prediction.currentData())

    def _toggle_pre(self, checked: bool) -> None:
        if self.pre_questions is not None:
            self.pre_questions.setVisible(checked)

    def _build_result(self) -> None:
        layout = QVBoxLayout(self.panels["Simular"])
        self.result_panel = ResultPanel()
        layout.addWidget(self.result_panel)
        self.intervene_button = button("Intervenir en el caso", "start_intervention", "primary")
        self.intervene_button.clicked.connect(lambda: self.intent.emit("phase", "Intervenir"))
        layout.addWidget(self.intervene_button)

    def _build_intervene(self) -> None:
        layout = QVBoxLayout(self.panels["Intervenir"])
        layout.addWidget(label(
            "Modifica los parámetros permitidos. La comparación conservará la configuración inicial original.",
        ))
        self.intervention_guidance = label("")
        layout.addWidget(self.intervention_guidance)
        self.editor_holder = QVBoxLayout()
        self.editor = None
        layout.addLayout(self.editor_holder)
        self.apply_button = button("Predecir este nuevo intento", "apply_changes", "primary")
        self.apply_button.clicked.connect(lambda: self.intent.emit("changes", self.editor.values()))
        layout.addWidget(self.apply_button)
        actions = QHBoxLayout()
        self.hint_button = button("Pista 1", "next_hint")
        self.hint_button.clicked.connect(lambda: self.intent.emit("hint", None))
        self.solution_button = button("Mostrar una solución", "reveal_solution")
        self.solution_button.clicked.connect(lambda: self.intent.emit("solution", None))
        actions.addWidget(self.hint_button)
        actions.addWidget(self.solution_button)
        layout.addLayout(actions)
        self.hints = label("")
        self.solution = label("")
        layout.addWidget(self.hints)
        layout.addWidget(self.solution)

    def _build_compare(self) -> None:
        layout = QVBoxLayout(self.panels["Comparar"])
        self.compare_guidance = label("")
        layout.addWidget(self.compare_guidance)
        self.comparison = table(("Evidencia", "Inicial", "Intento"), "comparison")
        self.changed_parameters = table(("Parámetro", "Inicial", "Intento", "Unidad"), "changes")
        self.compare_plot = TrajectoryPlot()
        self.history = table(("Intento", "Predicción", "Observado", "Cambios"), "history")
        layout.addWidget(label("Configuración inicial → intento actual", "title"))
        layout.addWidget(self.changed_parameters)
        layout.addWidget(self.compare_plot)
        layout.addWidget(disclosure("Evidencia comparada", self.comparison))
        layout.addWidget(disclosure("Intentos de este caso · solo en esta sesión", self.history))
        self.explain_button = button("Explicar lo observado", "open_explanation", "primary")
        self.explain_button.clicked.connect(lambda: self.intent.emit("phase", "Explicar"))
        layout.addWidget(self.explain_button)

    def _build_explain(self) -> None:
        layout = QVBoxLayout(self.panels["Explicar"])
        self.explain_guidance = label("")
        layout.addWidget(self.explain_guidance)
        self.debrief = label("")
        self.explanation = text_panel("explanation")
        self.clearing = text_panel("clearing_bracket")
        self.score = label("")
        self.post_holder = QVBoxLayout()
        self.post_questions = None
        layout.addWidget(self.debrief)
        layout.addWidget(label("Explicación y evidencia del intento", "title"))
        layout.addWidget(self.explanation)
        self.evidence = text_panel("explanation_evidence")
        layout.addWidget(disclosure("Evidencia avanzada del intento", self.evidence))
        layout.addWidget(self.clearing)
        layout.addWidget(label("Pregunta conceptual de cierre", "title"))
        layout.addLayout(self.post_holder)
        self.assess_button = button("Completar autoevaluación local", "finish_assessment")
        self.assess_button.clicked.connect(
            lambda: self.intent.emit("assessment", self.post_questions.values())
        )
        layout.addWidget(self.assess_button)
        layout.addWidget(self.score)
        self.retry_button = button("Explorar otra intervención", "retry", "primary")
        self.retry_button.clicked.connect(lambda: self.intent.emit("phase", "Intervenir"))
        layout.addWidget(self.retry_button)

    def reset_assessment(self) -> None:
        self.assess_enabled.setChecked(False)
        for editor in (self.pre_questions, self.post_questions):
            if editor is not None:
                for control in editor.inputs.values():
                    control.setCurrentIndex(0)

    def set_case(self, case: CaseView) -> None:
        changed = self.preview is None or self.preview.case_id != case.preview.case_id
        if changed:
            self.completed_phases = set()
            self.last_phase = None
        self.preview = case.preview
        self.concept.setText(case.preview.concept)
        self.title.setText(case.preview.title)
        self.difficulty.setText(case.preview.difficulty)
        self.objective.setText(case.preview.objective)
        self.context.setText(case.context)
        self.provenance.setText(case.provenance)
        fill_table(self.baseline, case.configuration)
        fill_table(self.advanced_baseline, case.advanced_configuration)
        guidance = dict(case.guidance)
        self.observe_preparation.set_case(case)
        self.predict_preparation.set_case(case)
        self.intervention_guidance.setText(guidance.get("intervene", ""))
        self.compare_guidance.setText(guidance.get("compare", ""))
        self.explain_guidance.setText(guidance.get("explain", ""))
        if changed:
            for plot in (self.result_panel.plot, self.compare_plot):
                plot.set_curves(())
            for view in (self.result_panel.configuration, self.comparison,
                         self.changed_parameters, self.history):
                fill_table(view, ())
            for control in (self.result_panel.status, self.result_panel.reason,
                            self.result_panel.prediction, self.debrief, self.score):
                control.clear()
            self.explanation.clear()
            self.clearing.clear()
            self.prediction.blockSignals(True)
            self.prediction.clear()
            self.prediction.addItem("Selecciona una predicción", None)
            for key, text, description in case.prediction_labels:
                self.prediction.addItem(text, key, description)
            self.prediction_help.setText("\n\n".join(
                f"{text}: {description}" for key, text, description in case.prediction_labels
            ))
            self.prediction.blockSignals(False)
            self.prediction_prompt.setText(case.prediction_prompt)
            self.assess_enabled.setChecked(False)
            for old in (self.editor, self.pre_questions, self.post_questions):
                if old is not None:
                    old.setParent(None)
                    old.deleteLater()
            self.editor = ParameterEditor(case.fields)
            self.editor_holder.addWidget(self.editor)
            self.pre_questions = QuestionEditor(case.questions, "pre")
            self.pre_holder.addWidget(self.pre_questions)
            self.pre_questions.hide()
            self.post_questions = QuestionEditor(case.questions, "post")
            self.post_holder.addWidget(self.post_questions)
            self.verticalScrollBar().setValue(0)
        self.solution_button.setVisible(case.has_solution)

    def render(self, *, phase: str, result: ResultView | None, prediction: str | None,
               hints: tuple[str, ...], solution: str, case: CaseView,
               history: tuple[tuple[str, ...], ...], assessment_pending: bool) -> None:
        self.set_case(case)
        if self.last_phase is not None and self.last_phase != phase:
            self.completed_phases.add(self.last_phase)
        self.last_phase = phase
        self.stage.setText(f"{PHASES.index(phase) + 1} / 6 · {phase}")
        for key, panel in self.panels.items():
            panel.setVisible(key == phase)
            self.steps[key].setChecked(key == phase)
            available = result is not None or key in ("Observar", "Predecir")
            self.steps[key].setEnabled(available)
            index = PHASES.index(key)
            state = "Actual" if key == phase else "Bloqueada" if not available else "Completada" if key in self.completed_phases else "Disponible"
            marker = "✓" if state == "Completada" else "·" if state == "Bloqueada" else str(index + 1)
            self.steps[key].setText(f"{marker}\n{key}")
            self.steps[key].setAccessibleName(f"{key} · {state}")
            self.steps[key].setToolTip(state)
            self.steps[key].setProperty("phase_state", state)
        self.prediction.blockSignals(True)
        self.prediction.setCurrentIndex(self.prediction.findData(prediction))
        self.prediction.blockSignals(False)
        self.run_button.setEnabled(prediction is not None)
        self.pending_changes.setText("Configuración que vas a simular: " + "; ".join(
            f"{item.label} = {number(item.value)}" for item in case.fields
        ))
        if getattr(self, "rendered_fields", None) != case.fields:
            self.editor.set_values(case.fields)
            self.rendered_fields = case.fields
        self.hints.setText("\n\n".join(f"Pista {i}: {text}" for i, text in enumerate(hints, 1)))
        self.hint_button.setText(f"Pista {min(len(hints) + 1, case.hints_available)}")
        self.hint_button.setEnabled(len(hints) < case.hints_available)
        self.solution.setText(solution)
        self.prediction_solution.setText(
            "Una solución pedagógica posible\n\n" + solution if solution else ""
        )
        self.prediction_solution.setVisible(bool(solution))
        self.assess_button.setVisible(assessment_pending)
        if result is not None:
            self.result_panel.render(result)
            fill_table(self.comparison, result.comparison)
            fill_table(self.changed_parameters, result.changes)
            fill_table(self.history, history)
            self.compare_plot.set_curves(result.curves)
            self.debrief.setText(result.debrief)
            self.explanation.setPlainText(result.explanation)
            self.evidence.setPlainText(result.advanced)
            self.clearing.setPlainText(result.clearing)
            self.clearing.setVisible(bool(result.clearing))
            self.score.setText(result.assessment)
        self.error.hide()


class FreeModePage(Page):
    browse_requested = Signal()
    intent = Signal(str, object)

    def __init__(self, fields: tuple[InputField, ...],
                 configuration: tuple[tuple[str, str], ...], advanced_configuration=(), parent=None) -> None:
        super().__init__("free", parent)
        self.body.addWidget(label("EXPLORACIÓN ABIERTA", "eyebrow"))
        self.body.addWidget(label("Modo libre", "heading"))
        self.body.addWidget(label(
            "Modelo clásico SMIB · configuración sintética del experimento de despeje. "
            "Edita inercia, despeje, horizonte y paso temporal. La condición inicial y los demás "
            "parámetros se conservan explícitamente.", "muted",
        ))
        self.browse_button = button("Explorar casos guiados", "free_browse_cases")
        self.browse_button.clicked.connect(self.browse_requested.emit)
        self.body.addWidget(self.browse_button)
        self.editor = ParameterEditor(fields)
        self.body.addWidget(self.editor)
        self.run_button = button("Simular", "run_free", "primary")
        self.run_button.clicked.connect(lambda: self.intent.emit("free", self.editor.values()))
        self.body.addWidget(self.run_button)
        self.error = label("", "error")
        self.error.setObjectName("free_error")
        self.error.hide()
        self.body.addWidget(self.error)
        self.retained_config = table(("Configuración de partida", "Valor"), "free_config")
        fill_table(self.retained_config, configuration)
        self.body.addWidget(disclosure("Parámetros de partida", self.retained_config))
        self.advanced_config = table(("Parámetro e identificador", "Valor"), "free_advanced")
        fill_table(self.advanced_config, advanced_configuration)
        self.body.addWidget(disclosure("Detalles avanzados · configuración completa", self.advanced_config))
        self.result_panel = ResultPanel()
        self.result_panel.hide()
        self.body.addWidget(self.result_panel)
        self.explanation = text_panel("free_explanation")
        self.explanation.hide()
        self.body.addWidget(self.explanation)
        self.body.addStretch()

    def render_result(self, result: ResultView) -> None:
        self.error.hide()
        self.result_panel.render(result)
        self.result_panel.show()
        self.explanation.setPlainText(result.explanation)
        self.explanation.show()
        self.ensureWidgetVisible(self.result_panel.status)
