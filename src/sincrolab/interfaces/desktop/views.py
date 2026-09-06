"""Scrollable shell views. No simulation or guided-learning workflow runs here."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from sincrolab.interfaces.desktop.presentation import CASE_PREVIEWS, CasePreview
from sincrolab.interfaces.desktop.widgets import CaseCard, button, label


class Page(QScrollArea):
    """Keep content reachable at small sizes and larger system scaling."""

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setProperty("role", "page")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(30, 28, 30, 28)
        self.body.setSpacing(16)
        self.setWidget(content)


class CatalogPage(Page):
    case_selected = Signal(str)
    browse_requested = Signal()
    free_requested = Signal()

    def __init__(self, *, home: bool, parent: QWidget | None = None) -> None:
        super().__init__("home" if home else "cases", parent)
        self.body.addWidget(label("LABORATORIO DE ESTABILIDAD TRANSITORIA", "eyebrow"))
        self.body.addWidget(label(
            "Comprende la respuesta del rotor" if home else "Casos guiados", "heading"
        ))
        self.body.addWidget(label(
            "SincroLab es un laboratorio educativo del modelo clásico de una máquina "
            "conectada a una barra infinita. Empieza por un concepto y explora su caso."
            if home else
            "Tres recorridos para estudiar el fenómeno. Selecciona una ficha para "
            "conocer su concepto, objetivo y dificultad.",
            "muted",
        ))
        if home:
            actions = QHBoxLayout()
            self.browse_button = button("Explorar casos guiados", "browse_cases", "primary")
            self.browse_button.clicked.connect(self.browse_requested.emit)
            actions.addWidget(self.browse_button)
            self.free_button = button("Modo libre", "open_free")
            self.free_button.clicked.connect(self.free_requested.emit)
            actions.addWidget(self.free_button)
            actions.addStretch()
            self.body.addLayout(actions)
            self.body.addWidget(label("Elige un punto de partida", "section"))
        self.cards = []
        for number, preview in enumerate(CASE_PREVIEWS, start=1):
            card = CaseCard(preview, number)
            card.selected.connect(self.case_selected.emit)
            self.body.addWidget(card)
            self.cards.append(card)
        self.body.addWidget(label(
            "Vista previa del laboratorio · Las fichas están disponibles; "
            "los ejercicios interactivos todavía no están habilitados.", "muted"
        ))
        self.body.addStretch()


class CaseDetailPage(Page):
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("case_detail", parent)
        self.preview: CasePreview | None = None
        self.back_button = button("Volver a casos guiados", "back_to_cases")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.body.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.concept = label("", "eyebrow")
        self.title = label("", "heading")
        self.difficulty = label("", "badge")
        self.objective = label("")
        self.body.addWidget(self.concept)
        self.body.addWidget(self.title)
        self.body.addWidget(self.difficulty, 0, Qt.AlignmentFlag.AlignLeft)
        self.body.addWidget(label("Objetivo de aprendizaje", "section"))
        self.body.addWidget(self.objective)
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(label("Acerca de este recorrido", "title"))
        layout.addWidget(label(
            "Esta ficha presenta el tema del caso. La predicción, la simulación "
            "y la comparación de intentos estarán disponibles en una próxima etapa.",
            "muted",
        ))
        layout.addWidget(label(
            "Caso educativo sintético. No representa una recomendación para operar "
            "una red eléctrica real.", "muted",
        ))
        self.body.addWidget(panel)
        self.body.addStretch()

    def set_preview(self, preview: CasePreview) -> None:
        self.preview = preview
        self.concept.setText(preview.concept)
        self.title.setText(preview.title)
        self.difficulty.setText(preview.difficulty)
        self.objective.setText(preview.objective)
        self.verticalScrollBar().setValue(0)


class FreeModePage(Page):
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("free", parent)
        self.body.addWidget(label("EXPLORACIÓN ABIERTA", "eyebrow"))
        self.body.addWidget(label("Modo libre", "heading"))
        self.body.addWidget(label(
            "Un espacio para plantear tus propios experimentos con el modelo "
            "educativo de SincroLab.", "muted",
        ))
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label("La simulación estará disponible próximamente", "section"))
        layout.addWidget(label(
            "Esta vista aún no permite introducir parámetros ni ejecutar experimentos. "
            "Por ahora, puedes explorar los conceptos y objetivos de los casos guiados.",
            "muted",
        ))
        self.browse_button = button("Explorar casos guiados", "free_browse_cases", "primary")
        self.browse_button.clicked.connect(self.browse_requested.emit)
        layout.addWidget(self.browse_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.body.addWidget(panel)
        self.body.addStretch()
