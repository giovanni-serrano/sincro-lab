"""Scrollable catalog views, populated by controller presentation data."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget, QHBoxLayout

from sincrolab.interfaces.desktop.presentation import CasePreview
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

    def __init__(self, previews: tuple[CasePreview, ...], *, home: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__("home" if home else "cases", parent)
        self.body.addWidget(label("LABORATORIO DE ESTABILIDAD TRANSITORIA", "eyebrow"))
        self.body.addWidget(label(
            "Comprende la respuesta del rotor" if home else "Casos guiados", "heading",
        ))
        self.body.addWidget(label(
            "Explora el modelo clásico de una máquina conectada a una barra infinita. "
            "Observa, predice y compara el efecto de tu intervención.", "muted",
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
        for number, preview in enumerate(previews, start=1):
            card = CaseCard(preview, number)
            card.selected.connect(self.case_selected.emit)
            self.body.addWidget(card)
            self.cards.append(card)
        self.body.addWidget(label(
            "Los casos y sus explicaciones conservan el texto original del núcleo. "
            "Tus intentos permanecen únicamente en esta sesión local.", "muted",
        ))
        self.body.addStretch()
