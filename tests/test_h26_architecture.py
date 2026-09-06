import ast
from importlib.resources import files
from pathlib import Path
import tomllib


ROOT = Path(__file__).parents[1]
SRC = ROOT / "src" / "sincrolab"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_core_has_no_ui_and_runtime_has_no_scipy_or_network_dependencies() -> None:
    forbidden_roots = {
        "scipy",
        "PySide6",
        "PyQt6",
        "requests",
        "httpx",
        "flask",
        "django",
        "fastapi",
        "react",
    }
    for path in SRC.rglob("*.py"):
        roots = {name.split(".", 1)[0] for name in _imports(path)}
        # H27 permits Qt only within the optional desktop adapter.
        forbidden = forbidden_roots - {"PySide6"} if path.is_relative_to(
            SRC / "interfaces" / "desktop"
        ) else forbidden_roots
        assert roots.isdisjoint(forbidden), path


def test_h23_projection_is_an_installed_package_resource() -> None:
    projection = files("sincrolab.application").joinpath(
        "_h23_reference_projection.json"
    )
    assert projection.is_file()


def test_portable_application_has_no_cli_or_interface_dependency() -> None:
    imports = _imports(SRC / "application" / "portable.py")
    assert all(not name.startswith("sincrolab.interfaces") for name in imports)


def test_console_entry_point_targets_thin_cli_adapter() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"] == {
        "sincrolab": "sincrolab.interfaces.cli:main"
    }


def test_scipy_remains_development_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert all(not item.startswith("scipy") for item in project["project"]["dependencies"])
    assert any(
        item.startswith("scipy") for item in project["dependency-groups"]["dev"]
    )
