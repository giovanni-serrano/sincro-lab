"""Paint canonical samples and configured events; no interpolation or diagnosis."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from sincrolab.interfaces.desktop.presentation import Curve, number
from sincrolab.interfaces.desktop.theme import COLORS


class TrajectoryPlot(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.curves: tuple[Curve, ...] = ()
        self.setMinimumHeight(480)
        self.setAccessibleName("Trayectorias calculadas")

    def set_curves(self, curves: tuple[Curve, ...]) -> None:
        self.curves = curves
        if curves:
            self.setAccessibleName("; ".join(curves[0].axis_labels))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLORS["surface"]))
        if not self.curves:
            return
        colors = (COLORS["muted"], COLORS["accent"]) if len(self.curves) > 1 else (COLORS["accent"],)
        for index, curve in enumerate(self.curves):
            pen = QPen(QColor(colors[index]), 2)
            if len(self.curves) > 1 and index == 0:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            x = 20 + index * 200
            painter.drawLine(x, 20, x + 24, 20)
            painter.drawText(x + 32, 25, curve.name)
        events = dict.fromkeys(item for curve in self.curves for item in curve.events)
        event_text = " · ".join(f"{title}: {number(time)} s" for title, time in events)
        event_area = painter.boundingRect(QRectF(16, 34, self.width() - 32, 100),
                                          Qt.TextFlag.TextWordWrap, event_text)
        painter.setPen(QColor("#865B1D"))
        painter.drawText(event_area, Qt.TextFlag.TextWordWrap, event_text)
        start = 52 + event_area.height()
        for panel, field in enumerate(("delta_rad", "omega_dev_pu")):
            top = start + panel * ((self.height() - start) / 2)
            area = QRectF(78, top + 18, max(10, self.width() - 108),
                          max(10, (self.height() - start) / 2 - 58))
            times = [value for curve in self.curves for value in curve.time_s]
            values = [value for curve in self.curves for value in getattr(curve, field)]
            xmin, xmax = min(times), max(times)
            ymin, ymax = min(values), max(values)
            # Extents and ticks are viewport geometry, not scientific metrics.
            xspan = xmax - xmin or 1.0
            yspan = ymax - ymin or 1.0
            painter.setPen(QColor(COLORS["ink"]))
            painter.drawText(16, int(top + 4), self.curves[0].axis_labels[panel] if self.curves[0].axis_labels else field)
            for tick in range(5):
                y = area.bottom() - area.height() * tick / 4
                x = area.left() + area.width() * tick / 4
                painter.setPen(QPen(QColor(COLORS["border"]), 1))
                painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
                painter.setPen(QColor(COLORS["muted"]))
                painter.drawText(QRectF(0, y - 10, 70, 20), Qt.AlignmentFlag.AlignRight,
                                 f"{ymin + yspan * tick / 4:.3g}")
                painter.drawText(QRectF(x - 25, area.bottom() + 5, 50, 20),
                                 Qt.AlignmentFlag.AlignCenter, f"{xmin + xspan * tick / 4:.3g}")
            painter.drawText(QRectF(area.left(), area.bottom() + 24, area.width(), 18),
                             Qt.AlignmentFlag.AlignCenter, "Tiempo (s)")
            # Events come directly from each retained configuration. Equal
            # markers share a label; distinct clearing times remain distinct.
            for title, time in events:
                if not xmin <= time <= xmax:
                    continue
                x = area.left() + (time - xmin) / xspan * area.width()
                painter.setPen(QPen(QColor(COLORS["event"]), 1, Qt.PenStyle.DotLine))
                painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
            painter.save()
            painter.setClipRect(area.adjusted(-1, -1, 1, 1))
            for index, curve in enumerate(self.curves):
                path = QPainterPath()
                for sample, (time, value) in enumerate(zip(curve.time_s, getattr(curve, field), strict=True)):
                    point = QPointF(area.left() + (time - xmin) / xspan * area.width(),
                                    area.bottom() - (value - ymin) / yspan * area.height())
                    path.moveTo(point) if sample == 0 else path.lineTo(point)
                pen = QPen(QColor(colors[index]), 1.8)
                if len(self.curves) > 1 and index == 0:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawPath(path)
            painter.restore()
