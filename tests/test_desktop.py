"""Optional Qt smoke and navigation checks; run with the desktop extra."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from sincrolab.interfaces.desktop.window import MainWindow


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setStyle("Fusion")
    yield instance


@pytest.fixture
def window(app):
    widget = MainWindow()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_window_starts_on_home_and_closes_cleanly(window, app):
    assert window.isVisible()
    assert "SincroLab" in window.windowTitle()
    assert window.stack.currentWidget() is window.home
    assert window.navigation_buttons["home"].isChecked()
    assert window.close()
    app.processEvents()
    assert not window.isVisible()


@pytest.mark.parametrize("destination", ["cases", "free", "home"])
def test_navigation_changes_visible_page_and_active_button(window, app, destination):
    pages = tuple(window.stack.widget(i) for i in range(window.stack.count()))
    for target in ("free", "cases", destination):
        QTest.mouseClick(window.navigation_buttons[target], Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window.stack.currentWidget() is window.pages[target]
        assert window.pages[target].isVisible()
        assert sum(item.isChecked() for item in window.navigation_buttons.values()) == 1
        assert window.navigation_buttons[target].isChecked()
    assert pages == tuple(window.stack.widget(i) for i in range(window.stack.count()))


def test_home_and_free_mode_actions_navigate(window, app):
    window.home.browse_button.click()
    assert window.stack.currentWidget() is window.cases
    window.navigate("home")
    window.home.free_button.click()
    assert window.stack.currentWidget() is window.free
    window.free.browse_button.click()
    app.processEvents()
    assert window.stack.currentWidget() is window.cases


@pytest.mark.parametrize("source", ["home", "cases"])
def test_each_card_opens_its_own_detail_and_returns_to_browser(window, app, source):
    catalog = window.pages[source]
    assert len(catalog.cards) == len(window.controller.catalog) == 3
    for card, preview in zip(catalog.cards, window.controller.catalog, strict=True):
        window.navigate(source)
        texts = {item.text() for item in card.findChildren(QLabel)}
        assert {preview.title, preview.concept, preview.objective, preview.difficulty} <= texts
        card.open_button.click()
        app.processEvents()
        assert window.stack.currentWidget() is window.detail
        assert window.detail.preview == preview
        assert window.detail.title.text() == preview.title
        assert window.detail.objective.text() == preview.objective
        assert window.detail.difficulty.text() == preview.difficulty
        assert window.navigation_buttons["cases"].isChecked()
        window.detail.back_button.click()
        assert window.stack.currentWidget() is window.cases


def test_unknown_case_does_not_change_navigation(window):
    window.open_case("missing")
    assert isinstance(window.last_error, ValueError)
    assert window.stack.currentWidget() is window.home


def test_keyboard_can_activate_navigation_and_card(window, app):
    control = window.navigation_buttons["cases"]
    control.setFocus()
    QTest.keyClick(control, Qt.Key.Key_Space)
    app.processEvents()
    assert window.stack.currentWidget() is window.cases
    card_button = window.cases.cards[0].open_button
    card_button.setFocus()
    QTest.keyClick(card_button, Qt.Key.Key_Space)
    app.processEvents()
    assert window.stack.currentWidget() is window.detail
    assert window.detail.back_button.hasFocus()
    QTest.keyClick(window.detail.back_button, Qt.Key.Key_Space)
    assert window.stack.currentWidget() is window.cases


@pytest.mark.parametrize("size", [(820, 620), (1160, 860)])
def test_content_remains_reachable_when_resized(window, app, size):
    window.resize(*size)
    for destination in ("home", "cases", "free"):
        window.navigate(destination)
        app.processEvents()
        page = window.pages[destination]
        assert page.widget().width() <= page.viewport().width()
        assert page.horizontalScrollBar().maximum() == 0
        if destination != "free":
            last = page.cards[-1].open_button
            page.ensureWidgetVisible(last)
            app.processEvents()
            visible_position = last.mapTo(page.viewport(), last.rect().center())
            assert page.viewport().rect().contains(visible_position)
