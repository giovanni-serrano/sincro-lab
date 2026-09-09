"""Reusable presentation widgets with navigation and selection signals only."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from sincrolab.interfaces.desktop.presentation import CasePreview


def label(text: str, role: str = "body") -> QLabel:
    widget = QLabel(text)
    widget.setProperty("role", role)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return widget


def button(text: str, name: str, role: str = "secondary") -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setProperty("role", role)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


class CaseCard(QFrame):
    """Compact catalog row emitting an ID without loading a scientific case."""

    selected = Signal(str)

    def __init__(self, preview: CasePreview, number: int, parent=None) -> None:
        super().__init__(parent)
        self.preview = preview
        self.setObjectName(f"card_{preview.case_id}")
        self.setProperty("role", "card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 18, 0, 18)
        layout.setSpacing(18)
        index = label(f"{number:02d}", "number")
        index.setFixedWidth(36)
        layout.addWidget(index, 0, Qt.AlignmentFlag.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(6)
        body.addWidget(label(preview.title, "title"))
        body.addWidget(label(preview.objective, "muted"))
        metadata = QHBoxLayout()
        metadata.addWidget(label(preview.concept, "badge"), 1)
        metadata.addWidget(label(preview.difficulty, "badge"))
        body.addLayout(metadata)
        layout.addLayout(body, 1)
        self.open_button = button("Abrir →", f"open_{preview.case_id}")
        self.open_button.setAccessibleName(f"Ver caso: {preview.title}")
        self.open_button.clicked.connect(lambda: self.selected.emit(preview.case_id))
        layout.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignVCenter)


class PredictionChoices(QWidget):
    """Exclusive radio rows retaining the view's indexed selection contract."""

    currentIndexChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.group = QButtonGroup(self)
        self.options = []
        self.rows = []
        self.group.idClicked.connect(self._selected)

    def clear(self) -> None:
        for row, radio in self.rows:
            self.group.removeButton(radio)
            self.layout.removeWidget(row)
            row.deleteLater()
        self.rows = []
        self.options = []

    def addItem(self, text: str, key, description: str = "") -> None:
        index = len(self.options)
        self.options.append((text, key))
        if key is None:
            return
        row = QFrame()
        row.setProperty("role", "choice")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 2, 12, 10)
        layout.setSpacing(0)
        radio = QRadioButton(text)
        radio.setAccessibleName(text + ". " + description)
        self.group.addButton(radio, index)
        layout.addWidget(radio)
        layout.addWidget(label(description, "muted"))
        self.layout.addWidget(row)
        self.rows.append((row, radio))

    def _selected(self, index: int) -> None:
        for row, radio in self.rows:
            row.setProperty("selected", radio.isChecked())
            row.style().unpolish(row)
            row.style().polish(row)
        self.currentIndexChanged.emit()

    def setCurrentIndex(self, index: int) -> None:
        self.group.setExclusive(False)
        for row, radio in self.rows:
            radio.setChecked(self.group.id(radio) == index)
        self.group.setExclusive(True)
        self._selected(index)

    def currentData(self):
        index = self.group.checkedId()
        return self.itemData(index) if index >= 0 else None

    def findData(self, key) -> int:
        return next((i for i, (_, value) in enumerate(self.options) if value == key), -1)

    def itemData(self, index: int):
        return self.options[index][1]

    def itemText(self, index: int) -> str:
        return self.options[index][0]

    def count(self) -> int:
        return len(self.options)
