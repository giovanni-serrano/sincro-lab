"""Reusable presentation widgets with navigation signals only."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
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
    """A preview card that emits an ID without loading a scientific case."""

    selected = Signal(str)

    def __init__(self, preview: CasePreview, number: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview = preview
        self.setObjectName(f"card_{preview.case_id}")
        self.setProperty("role", "card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(18)
        index = label(f"{number:02d}", "number")
        index.setFixedWidth(32)
        layout.addWidget(index, 0, Qt.AlignmentFlag.AlignTop)
        body = QVBoxLayout()
        body.setSpacing(7)
        header = QHBoxLayout()
        header.addWidget(label(preview.concept, "eyebrow"), 1)
        badge = label(preview.difficulty, "badge")
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)
        body.addWidget(label(preview.title, "title"))
        body.addWidget(label(preview.objective, "muted"))
        self.open_button = button("Ver caso", f"open_{preview.case_id}")
        self.open_button.setAccessibleName(f"Ver caso: {preview.title}")
        self.open_button.clicked.connect(lambda: self.selected.emit(preview.case_id))
        body.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(body, 1)
