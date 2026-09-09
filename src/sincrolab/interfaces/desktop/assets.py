"""Read the same audited presentation assets served by the static web assembly."""

from importlib.resources import files
import json

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from sincrolab.interfaces.desktop.widgets import label


def asset_bytes(name: str) -> bytes:
    return files("sincrolab.interfaces").joinpath("assets", name).read_bytes()


DESIGN = json.loads(asset_bytes("design.json"))


class Diagram(QWidget):
    """Scale conceptual line art without inferring any scientific values."""

    def __init__(self, key: str, parent=None) -> None:
        super().__init__(parent)
        metadata = DESIGN["diagrams"][key]
        self.setObjectName(f"diagram_{key}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.addWidget(label(metadata["title"], "title"))
        self.svg = QSvgWidget()
        self.svg.load(QByteArray(asset_bytes(metadata["file"])))
        # Preserve circles and relative angles when the layout caps the height.
        self.svg.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.svg.setAccessibleName(metadata["title"] + ". " + metadata["caption"])
        self.svg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.svg)
        layout.addWidget(label(metadata["caption"], "caption"))

    def resizeEvent(self, event) -> None:
        box = self.svg.renderer().viewBoxF()
        self.svg.setFixedHeight(min(280, round(self.width() * box.height() / box.width())))
        super().resizeEvent(event)


def navigation_icon(key: str, color: str = "#FFFCF5") -> QIcon:
    paths = {
        "home": 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
        "learn": 'M12 5v16M12 5C8 2 4 3 2 4v15c4-2 7-1 10 2 3-3 6-4 10-2V4c-2-1-6-2-10 1Z',
        "cases": 'M5 2h10l4 4v16H5ZM14 2v6h5M8 12h8M8 16h8',
        "free": 'M3 6h18M3 12h18M3 18h18M8 3v6M16 9v6M10 15v6',
    }
    data = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{paths[key]}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    icon = QIcon()
    for mode, tint in ((QIcon.Mode.Normal, color), (QIcon.Mode.Active, color),
                       (QIcon.Mode.Selected, "#102D3B")):
        pixmap = QPixmap(QSize(24, 24))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(data.replace(color, tint).encode())).render(painter)
        painter.end()
        icon.addPixmap(pixmap, mode, QIcon.State.Off)
        selected = QPixmap(QSize(24, 24))
        selected.fill(Qt.GlobalColor.transparent)
        painter = QPainter(selected)
        QSvgRenderer(QByteArray(data.replace(color, "#102D3B").encode())).render(painter)
        painter.end()
        icon.addPixmap(selected, mode, QIcon.State.On)
    return icon
