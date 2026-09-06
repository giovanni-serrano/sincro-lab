"""Desktop architecture and core-only behavior, runnable without Qt installed."""

import ast
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib


ROOT = Path(__file__).parents[1]
DESKTOP = ROOT / "src/sincrolab/interfaces/desktop"


def test_desktop_imports_only_presentation_qt_and_small_stdlib_surface():
    allowed = {"sys", "dataclasses", "PySide6.QtCore", "PySide6.QtWidgets"}
    for path in DESKTOP.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, path
                modules = [node.module]
            else:
                continue
            for module in modules:
                assert module in allowed or module.startswith(
                    "sincrolab.interfaces.desktop."
                ), (path, module)
        assert not any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec", "compile"}
            for node in ast.walk(tree)
        ), path


def test_desktop_extra_preserves_numpy_only_base_runtime():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["dependencies"] == ["numpy>=1.26,<3"]
    assert metadata["project"]["optional-dependencies"]["desktop"] == ["PySide6>=6,<7"]
    assert "desktop" not in metadata["dependency-groups"]


def test_preview_contract_contains_only_editorial_metadata():
    from dataclasses import fields
    from sincrolab.interfaces.desktop.presentation import CASE_PREVIEWS, CasePreview

    assert {field.name for field in fields(CasePreview)} == {
        "case_id", "title", "concept", "objective", "difficulty",
    }
    assert len({item.case_id for item in CASE_PREVIEWS}) == len(CASE_PREVIEWS)
    for preview in CASE_PREVIEWS:
        assert all(isinstance(getattr(preview, field.name), str)
                   and getattr(preview, field.name).strip() for field in fields(preview))


def test_core_cli_and_desktop_error_without_qt():
    script = textwrap.dedent("""
        import importlib.abc
        import sys
        class NoQt(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] == 'PySide6':
                    raise ModuleNotFoundError('Qt intentionally unavailable', name='PySide6')
        sys.meta_path.insert(0, NoQt())
        import sincrolab
        import sincrolab.interfaces.desktop
        from sincrolab.interfaces.cli import main as cli_main
        assert cli_main(['capabilities']) == 0
        assert cli_main(['reference', 'run', 'stable_transient']) == 0
        assert not any(name.startswith('PySide6') for name in sys.modules)
        from sincrolab.interfaces.desktop.app import main
        assert main([]) == 2
        assert not any(name.startswith('PySide6') for name in sys.modules)
    """)
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "uv sync --locked --extra desktop" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_constructing_and_navigating_desktop_never_loads_scientific_modules():
    script = textwrap.dedent("""
        import importlib.abc
        import importlib.util
        import os
        import sys
        if importlib.util.find_spec('PySide6') is None:
            raise SystemExit(77)
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        forbidden = ('sincrolab.application', 'sincrolab.models', 'sincrolab.numerical',
                     'sincrolab.analysis', 'sincrolab.simulation', 'numpy', 'scipy')
        class NoScience(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if any(fullname == root or fullname.startswith(root + '.') for root in forbidden):
                    raise AssertionError('Desktop attempted science import: ' + fullname)
        sys.meta_path.insert(0, NoScience())
        from PySide6.QtWidgets import QApplication
        from sincrolab.interfaces.desktop.window import MainWindow
        app = QApplication([])
        window = MainWindow()
        window.show()
        for destination in ('home', 'cases', 'free'):
            window.navigate(destination)
            app.processEvents()
        window.home.cards[0].open_button.click()
        assert window.stack.currentWidget() is window.detail
        assert not any(name == root or name.startswith(root + '.')
                       for name in sys.modules for root in forbidden)
        window.close()
    """)
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    if completed.returncode == 77:
        import pytest
        pytest.skip("Install the desktop extra to exercise Qt import isolation")
    assert completed.returncode == 0, completed.stderr


def test_module_entry_point_runs_event_loop_and_exits_cleanly():
    script = textwrap.dedent("""
        import importlib.util
        import os
        import runpy
        if importlib.util.find_spec('PySide6') is None:
            raise SystemExit(77)
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        original_exec = QApplication.exec
        def bounded_exec(self):
            assert len(self.topLevelWidgets()) == 1
            window = self.topLevelWidgets()[0]
            assert window.isVisible()
            QTimer.singleShot(0, window.close)
            return original_exec()
        QApplication.exec = bounded_exec
        runpy.run_module('sincrolab.interfaces.desktop', run_name='__main__')
    """)
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
    )
    if completed.returncode == 77:
        import pytest
        pytest.skip("Install the desktop extra to exercise the event loop")
    assert completed.returncode == 0, completed.stderr
