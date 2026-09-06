"""Small shared palette and widget roles for the desktop shell."""

COLORS = {
    "ink": "#172C3A",
    "muted": "#526471",
    "ocean": "#086B88",
    "ocean_hover": "#07556D",
    "tint": "#E8F3F7",
    "surface": "#F4F6F8",
    "border": "#D6DFE5",
    "white": "#FFFFFF",
}

STYLE_SHEET = """
QWidget { color: %(ink)s; font-family: "Segoe UI", sans-serif; font-size: 14px; }
QMainWindow, QStackedWidget, QScrollArea, QWidget[role="page"] {
    background: %(white)s;
}
QFrame[role="sidebar"] { background: %(surface)s; border-right: 1px solid %(border)s; }
QLabel { background: transparent; }
QLabel[role="brand"] { font-size: 24px; font-weight: 700; }
QLabel[role="eyebrow"] { color: %(ocean)s; font-size: 12px; font-weight: 600; }
QLabel[role="heading"] { font-size: 30px; font-weight: 600; }
QLabel[role="section"] { font-size: 20px; font-weight: 600; }
QLabel[role="title"] { font-size: 18px; font-weight: 600; }
QLabel[role="muted"] { color: %(muted)s; }
QLabel[role="badge"] {
    color: %(ocean_hover)s; background: %(tint)s; border-radius: 5px;
    padding: 4px 8px; font-size: 12px; font-weight: 600;
}
QLabel[role="number"] { color: %(ocean)s; font-size: 20px; font-weight: 600; }
QFrame[role="card"], QFrame[role="panel"] {
    background: %(white)s; border: 1px solid %(border)s; border-radius: 8px;
}
QFrame[role="panel"] { background: %(surface)s; }
QPushButton {
    background: %(white)s; border: 1px solid %(border)s; border-radius: 6px;
    padding: 9px 14px; font-weight: 600; min-height: 20px;
}
QPushButton:hover { background: %(tint)s; border-color: %(ocean)s; }
QPushButton:pressed { background: %(border)s; }
QPushButton:focus { border: 2px solid %(ocean)s; }
QPushButton[role="primary"] { background: %(ocean)s; color: %(white)s; border-color: %(ocean)s; }
QPushButton[role="primary"]:hover { background: %(ocean_hover)s; }
QPushButton[role="primary"]:focus { border: 2px solid %(ink)s; }
QPushButton[role="nav"] { text-align: left; background: transparent; border: 2px solid transparent; }
QPushButton[role="nav"]:checked { background: %(tint)s; color: %(ocean_hover)s; }
QPushButton[role="nav"]:hover { background: %(tint)s; }
QPushButton[role="nav"]:focus { border-color: %(ocean)s; }
QScrollArea { border: none; }
QLineEdit, QComboBox, QPlainTextEdit {
    background: %(white)s; border: 1px solid %(border)s; border-radius: 4px;
    padding: 7px; selection-background-color: %(ocean)s;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: %(ocean)s; }
QPushButton:checked { background: %(tint)s; border-color: %(ocean)s; }
QPushButton:disabled { color: %(muted)s; background: %(surface)s; border-color: %(border)s; }
QLabel[role="error"] { color: #8A321F; background: #FFF1EA; padding: 10px; }
QTableWidget { background: %(white)s; border: 1px solid %(border)s; gridline-color: %(border)s; }
QHeaderView::section { background: %(surface)s; border: none; padding: 6px; }

""" % COLORS
