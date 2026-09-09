"""Widget roles using the shared warm canvas and petrol navigation palette."""

from sincrolab.interfaces.desktop.assets import DESIGN

COLORS = DESIGN["colors"]

STYLE_SHEET = """
QWidget { color: %(ink)s; font-family: "Segoe UI"; font-size: 14px; }
QMainWindow, QStackedWidget, QScrollArea, QWidget[role="page"] { background: %(canvas)s; }
QLabel { background: transparent; }
QLabel[role="brand"] { font-size: 24px; font-weight: 600; color: %(surface)s; }
QLabel[role="sidebar_note"] { color: #DEE9EB; font-size: 12px; }
QLabel[role="eyebrow"] { color: %(accent)s; font-size: 11px; font-weight: 700; }
QLabel[role="heading"] { font-size: 30px; font-weight: 600; }
QLabel[role="section"] { font-size: 20px; font-weight: 600; }
QLabel[role="title"] { font-size: 17px; font-weight: 600; }
QLabel[role="muted"], QLabel[role="caption"] { color: %(muted)s; }
QLabel[role="caption"] { font-size: 12px; }
QLabel[role="badge"] { color: %(muted)s; font-size: 12px; padding: 4px 0; }
QLabel[role="number"] { color: %(accent)s; font-size: 26px; font-weight: 600; }
QFrame[role="sidebar"] { background: %(sidebar)s; border: none; }
QFrame[role="card"] { border: none; border-bottom: 1px solid %(border)s; background: transparent; }
QFrame[role="panel"] { background: %(surface_muted)s; border: 1px solid %(border)s; border-radius: 6px; }
QFrame[role="key-idea"] { background: %(accent_soft)s; border-left: 3px solid %(accent)s; }
QFrame[role="equation"] { background: %(surface)s; border-top: 1px solid %(border)s; border-bottom: 1px solid %(border)s; }
QFrame[role="reflection"] { border-left: 3px solid %(event)s; background: transparent; }
QLabel[role="equation_text"] { font-size: 19px; padding: 12px 0; }
QPushButton { background: %(surface)s; border: 1px solid %(border)s; border-radius: 5px; padding: 8px 12px; font-weight: 600; min-height: 22px; }
QPushButton:hover { background: %(accent_soft)s; border-color: %(accent)s; }
QPushButton:pressed { background: %(border)s; }
QPushButton:focus { border: 2px solid %(accent)s; }
QPushButton[role="primary"] { background: %(accent)s; color: %(surface)s; border-color: %(accent)s; }
QPushButton[role="primary"]:hover { background: %(accent_hover)s; }
QPushButton[role="primary"]:focus { border: 2px solid %(ink)s; }
QPushButton[role="link"] { text-align: left; border: 1px solid transparent; background: transparent; color: %(accent)s; padding: 6px 2px; }
QPushButton[role="link"]:focus { border-color: %(accent)s; }
QPushButton[role="nav"] { text-align: left; color: %(surface)s; background: transparent; border: 1px solid transparent; padding: 10px 6px; font-weight: 400; }
QPushButton[role="nav"]:checked { background: %(accent_soft)s; color: %(ink)s; font-weight: 600; }
QPushButton[role="nav"]:hover { background: #476D7E; color: %(surface)s; }
QPushButton[role="nav"]:focus { border-color: %(surface)s; }
QPushButton[role="step"] { border: none; border-bottom: 2px solid %(border)s; border-radius: 0; background: transparent; padding: 8px 1px; font-size: 12px; font-weight: 400; }
QPushButton[role="step"]:checked { border-bottom-color: %(accent)s; color: %(accent)s; font-weight: 700; background: %(accent_soft)s; }
QPushButton[role="step"]:focus { border: 1px solid %(accent)s; }
QPushButton[role="topic"] { border: none; border-left: 2px solid transparent; border-radius: 0; background: transparent; text-align: left; font-size: 12px; font-weight: 400; padding: 7px; }
QPushButton[role="topic"]:checked { border-left-color: %(accent)s; background: %(accent_soft)s; color: %(ink)s; }
QPushButton[role="topic"]:focus { border: 1px solid %(accent)s; }
QPushButton:disabled { color: %(muted)s; background: %(surface_muted)s; border-color: %(border)s; }
QScrollArea { border: none; }
QLineEdit, QComboBox, QPlainTextEdit { background: %(surface)s; border: 1px solid %(border)s; border-radius: 4px; padding: 8px; selection-background-color: %(accent)s; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid %(accent)s; }
QRadioButton { background: transparent; spacing: 10px; font-weight: 600; padding: 8px 0; }
QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid %(muted)s; border-radius: 9px; background: %(surface)s; }
QRadioButton::indicator:checked { background: %(accent)s; border: 2px solid %(surface)s; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid %(muted)s; border-radius: 2px; background: %(surface)s; }
QCheckBox::indicator:checked { background: %(accent)s; }
QRadioButton:focus { border: 1px solid %(accent)s; }
QFrame[role="choice"] { border: 1px solid %(border)s; border-radius: 6px; background: %(surface)s; }
QFrame[role="choice"][selected="true"] { border-color: %(accent)s; background: %(accent_soft)s; }
QCheckBox { spacing: 8px; padding: 7px 0; }
QCheckBox:focus { border: 1px solid %(accent)s; }
QLabel[role="error"] { color: #863B3A; background: #F8E9E5; padding: 12px; }
QLabel[role="result_status"] { font-size: 21px; font-weight: 600; padding: 12px; border-left: 3px solid %(muted)s; background: %(surface)s; }
QLabel[role="result_status"][status="stable"] { color: %(stable)s; border-color: %(stable)s; }
QLabel[role="result_status"][status="unstable"] { color: %(unstable)s; border-color: %(unstable)s; }
QLabel[role="result_status"][status="indeterminate"] { color: %(indeterminate)s; border-color: %(indeterminate)s; }
QTableWidget { background: %(surface)s; border: none; gridline-color: %(border)s; font-size: 13px; }
QHeaderView::section { background: %(surface_muted)s; border: none; padding: 7px; font-size: 12px; }
QStatusBar { background: %(surface_muted)s; color: %(muted)s; font-size: 11px; }
""" % COLORS
