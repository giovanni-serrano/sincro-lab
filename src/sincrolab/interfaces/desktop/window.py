"""Main window owning presentation navigation, never scientific state."""

from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from sincrolab.interfaces.desktop.presentation import CASE_PREVIEWS
from sincrolab.interfaces.desktop.theme import STYLE_SHEET
from sincrolab.interfaces.desktop.views import CatalogPage, CaseDetailPage, FreeModePage
from sincrolab.interfaces.desktop.widgets import button, label


class MainWindow(QMainWindow):
    """Reuse a fixed set of pages and expose explicit navigation destinations."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SincroLab — Laboratorio educativo")
        self.resize(1160, 860)
        self.setMinimumSize(820, 620)
        self.setStyleSheet(STYLE_SHEET)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setProperty("role", "sidebar")
        sidebar.setFixedWidth(214)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(18, 28, 18, 24)
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
        navigation.addWidget(label("DESKTOP · VISTA PREVIA", "eyebrow"))
        navigation.addWidget(label("Modelo educativo clásico SMIB", "muted"))
        layout.addWidget(sidebar)
        self.stack = QStackedWidget()
        self.home = CatalogPage(home=True)
        self.cases = CatalogPage(home=False)
        self.free = FreeModePage()
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
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)
        self.navigate("home")

    def navigate(self, destination: str) -> None:
        """Change the visible section without rebuilding widgets."""
        page = self.pages[destination]
        self.stack.setCurrentWidget(page)
        self.navigation_buttons[destination].setChecked(True)
        self.navigation_buttons[destination].setFocus()

    def open_case(self, case_id: str) -> None:
        """Display an editorial preview; no application operation is invoked."""
        preview = next((item for item in CASE_PREVIEWS if item.case_id == case_id), None)
        if preview is None:
            raise ValueError(f"Unknown case preview: {case_id}")
        self.detail.set_preview(preview)
        self.stack.setCurrentWidget(self.detail)
        self.navigation_buttons["cases"].setChecked(True)
        self.detail.back_button.setFocus()
