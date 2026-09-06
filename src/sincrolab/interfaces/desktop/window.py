"""Main window composing views, navigation and one portable controller."""

from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from sincrolab.interfaces.desktop.theme import STYLE_SHEET
from sincrolab.interfaces.desktop.views import CatalogPage
from sincrolab.interfaces.desktop.workflow import CaseDetailPage, FreeModePage
from sincrolab.interfaces.desktop.widgets import button, label
from sincrolab.interfaces.desktop.worker import OperationWorker


class MainWindow(QMainWindow):
    """Keep navigation separate from controller-owned requests and results."""

    def __init__(self, controller: "DesktopController | None" = None) -> None:
        super().__init__()
        if controller is None:
            from sincrolab.interfaces.desktop.adapter import DesktopController
            controller = DesktopController()
        self.controller = controller
        self.worker = None
        self.operation = ""
        self.last_error: BaseException | None = None
        self.setWindowTitle("SincroLab — Laboratorio educativo")
        self.resize(1160, 860)
        self.setMinimumSize(820, 620)
        self.setStyleSheet(STYLE_SHEET)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setProperty("role", "sidebar")
        self.sidebar.setFixedWidth(190)
        navigation = QVBoxLayout(self.sidebar)
        navigation.setContentsMargins(16, 28, 16, 24)
        navigation.setSpacing(10)
        navigation.addWidget(label("SincroLab", "brand"))
        navigation.addWidget(label("Laboratorio educativo", "muted"))
        navigation.addSpacing(32)
        self.navigation_group = QButtonGroup(self)
        self.navigation_buttons = {}
        for key, title in (("home", "Inicio"), ("cases", "Casos guiados"), ("free", "Modo libre")):
            control = button(title, f"nav_{key}", "nav")
            control.setCheckable(True)
            control.clicked.connect(lambda checked=False, page=key: self.navigate(page))
            self.navigation_group.addButton(control)
            self.navigation_buttons[key] = control
            navigation.addWidget(control)
        navigation.addStretch()
        navigation.addWidget(label("DESKTOP · LABORATORIO", "eyebrow"))
        navigation.addWidget(label("Modelo educativo clásico SMIB", "muted"))
        navigation.addWidget(label("Historial solo en memoria", "muted"))
        layout.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.home = CatalogPage(self.controller.catalog, home=True)
        self.cases = CatalogPage(self.controller.catalog, home=False)
        self.free = FreeModePage(self.controller.free_fields(), self.controller.free_configuration())
        self.detail = CaseDetailPage()
        self.pages = {"home": self.home, "cases": self.cases, "free": self.free}
        for page in (*self.pages.values(), self.detail):
            self.stack.addWidget(page)
        for page in (self.home, self.cases):
            page.case_selected.connect(self.open_case)
        self.home.browse_requested.connect(lambda: self.navigate("cases"))
        self.home.free_requested.connect(lambda: self.navigate("free"))
        self.free.browse_requested.connect(lambda: self.navigate("cases"))
        self.detail.back_requested.connect(lambda: self.navigate("cases"))
        self.detail.intent.connect(self.handle_intent)
        self.free.intent.connect(self.handle_intent)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)
        self.statusBar().showMessage("Listo · No se ha ejecutado ninguna simulación.")
        self.navigate("home")

    def navigate(self, destination: str) -> None:
        if self.worker is not None:
            return
        self.stack.setCurrentWidget(self.pages[destination])
        self.navigation_buttons[destination].setChecked(True)
        self.navigation_buttons[destination].setFocus()

    def open_case(self, case_id: str) -> None:
        if self.worker is not None:
            return
        try:
            self.controller.select_case(case_id)
        except (ValueError, TypeError) as error:
            self._show_error(error)
            return
        self.last_error = None
        self.statusBar().showMessage("Caso activo · historial solo en esta sesión.")
        self._render_guided()
        self.stack.setCurrentWidget(self.detail)
        self.navigation_buttons["cases"].setChecked(True)
        self.detail.back_button.setFocus()

    def _render_guided(self) -> None:
        controller = self.controller
        self.detail.render(
            phase=controller.phase, result=controller.result_view(),
            prediction=controller.prediction, hints=controller.hints,
            solution=controller.solution_text(), case=controller.case_view(),
            history=controller.history_rows(),
            assessment_pending=controller.completed_pre_answers is not None,
        )

    def handle_intent(self, action: str, payload: object) -> None:
        if self.worker is not None:
            return
        try:
            if action == "prediction":
                self.controller.prediction = payload
                return
            if action == "phase":
                self.controller.go_to(payload)
            elif action == "changes":
                self.controller.set_changes(payload)
                self.detail.reset_assessment()
            elif action == "hint":
                self.controller.reveal_hint()
            elif action == "solution":
                self.controller.reveal_solution()
                self.detail.reset_assessment()
            elif action == "run":
                self.controller.prepare(payload["prediction"], payload["pre"])
                self._start(self.controller.guided_job(), "guided")
                return
            elif action == "assessment":
                self._start(self.controller.assessment_job(payload), "assessment")
                return
            elif action == "free":
                self._start(self.controller.prepare_free(payload), "free")
                return
            else:
                raise ValueError(f"Acción desconocida: {action}")
            self._render_guided()
        except (ValueError, TypeError, ArithmeticError, RuntimeError) as error:
            self._show_error(error)

    def _start(self, job, operation: str) -> None:
        self.last_error = None
        self.operation = operation
        self.detail.error.hide()
        self.free.error.hide()
        self.sidebar.setEnabled(False)
        self.stack.setEnabled(False)
        self.statusBar().showMessage(
            "Simulando… conserva esta ventana abierta. Los datos permanecen locales."
            if operation != "assessment" else
            "Completando pre/post: se repite la misma ejecución para obtener la puntuación."
        )
        self.worker = OperationWorker(job, self)
        self.worker.succeeded.connect(self._completed)
        self.worker.rejected.connect(self._show_error)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: object) -> None:
        try:
            if self.operation == "free":
                self.controller.accept_free(result)
                self.free.render_result(self.controller.free_result_view())
            else:
                self.controller.accept_guided(result, assessment=self.operation == "assessment")
                self._render_guided()
                self.detail.verticalScrollBar().setValue(0)
        except (ValueError, TypeError, ArithmeticError, RuntimeError) as error:
            self._show_error(error)

    def _finished(self) -> None:
        self.worker.deleteLater()
        self.worker = None
        self.sidebar.setEnabled(True)
        self.stack.setEnabled(True)
        if self.last_error is None:
            self.statusBar().showMessage("Ejecución completada · resultados del núcleo portable.")

    def _show_error(self, error: BaseException) -> None:
        self.last_error = error
        message = f"No se completó la operación. {type(error).__name__}: {error}"
        target = self.free if self.stack.currentWidget() is self.free else self.detail
        target.error.setText(message)
        target.error.show()
        target.ensureWidgetVisible(target.error)
        self.statusBar().showMessage(message)

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            event.ignore()
            self.statusBar().showMessage("La ejecución sigue activa. Podrás cerrar al finalizar.")
        else:
            super().closeEvent(event)
