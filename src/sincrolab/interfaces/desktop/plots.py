"""Qt painting of returned samples only; no interpolation or derived science."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from sincrolab.interfaces.desktop.presentation import Curve, number


class TrajectoryPlot(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.curves: tuple[Curve, ...] = ()
        self.setMinimumHeight(360)
        self.setAccessibleName("Trayectorias de delta_rad y omega_dev_pu frente a time_s")

    def set_curves(self, curves: tuple[Curve, ...]) -> None:
        self.curves = curves
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self.curves:
            return
        colors = ("#71818D", "#086B88") if len(self.curves) > 1 else ("#086B88",)
        for index, curve in enumerate(self.curves):
            painter.setPen(QColor(colors[index]))
            painter.drawText(80 + index * 160, 20, curve.name)
        for panel, field in enumerate(("delta_rad", "omega_dev_pu")):
            top = 42 + panel * ((self.height() - 48) / 2)
            area = QRectF(84, top + 14, max(10, self.width() - 108),
                          max(10, (self.height() - 48) / 2 - 52))
            times = [value for curve in self.curves for value in curve.time_s]
            values = [value for curve in self.curves for value in getattr(curve, field)]
            xmin, xmax = min(times), max(times)
            ymin, ymax = min(values), max(values)
            # Bounds below serve only screen coordinates, never domain tolerance.
            xspan = xmax - xmin or 1.0
            yspan = ymax - ymin or 1.0
            painter.setPen(QColor("#526471"))
            painter.drawText(8, int(top + 4), field)
            painter.drawText(4, int(area.top() + 10), f"{ymax:.4g}")
            painter.drawText(4, int(area.bottom()), f"{ymin:.4g}")
            painter.drawText(int(area.left()), int(area.bottom() + 23), number(xmin))
            painter.drawText(int(area.right() - 85), int(area.bottom() + 23),
                             f"{number(xmax)} s")
            painter.setPen(QPen(QColor("#D6DFE5"), 1))
            painter.drawRect(area)
            painter.save()
            painter.setClipRect(area)
            for index, curve in enumerate(self.curves):
                path = QPainterPath()
                for sample, (time, value) in enumerate(zip(
                    curve.time_s, getattr(curve, field), strict=True,
                )):
                    point = QPointF(
                        area.left() + (time - xmin) / xspan * area.width(),
                        area.bottom() - (value - ymin) / yspan * area.height(),
                    )
                    if sample == 0:
                        path.moveTo(point)
                    else:
                        path.lineTo(point)
                pen = QPen(QColor(colors[index]), 1.8)
                if len(self.curves) > 1 and index == 0:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawPath(path)
            painter.restore()
