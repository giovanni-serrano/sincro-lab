from datetime import date
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib

from sincrolab.application.portable import get_capabilities


ROOT = Path(__file__).parents[1]


def test_readme_documents_portable_core_and_scientific_limits() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "modelo clásico",
        "SMIB",
        "INDETERMINATE",
        "Equal Area",
        "stable_t_clear_s < unstable_t_clear_s",
        "time_tolerance_s",
        "API de aplicación portable",
        "guided",
        "CLI",
        "all_reported_observations_match_expected",
        "proyección empaquetada completa",
        "no es un cálculo completo de cortocircuito",
        "H27 incorpora un shell desktop",
        "Web estática H29",
        "Pyodide 0.27.7",
        "No existe backend científico",
    ):
        assert required in readme
    assert "CCT exacto universal" not in readme
    assert "validación industrial" not in readme


def test_readme_cli_examples_execute() -> None:
    commands = (
        ("--help",),
        ("capabilities",),
        ("guided", "list"),
        ("guided", "show", "controlled-inertia-effect"),
        ("guided", "hints", "late-clearing-bracket", "--count", "1"),
        ("reference", "list"),
        ("reference", "show", "stable_transient"),
        ("reference", "run", "stable_transient"),
    )
    for arguments in commands:
        completed = subprocess.run(
            [sys.executable, "-m", "sincrolab.interfaces.cli", *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, (arguments, completed.stderr)


def test_readme_python_examples_execute() -> None:
    first = """
from sincrolab.application import (
    GuidedAttemptRequest, ParameterValueDTO, get_guided_case,
    run_portable_guided_attempt,
)
guided_case = get_guided_case("controlled-inertia-effect")
request = GuidedAttemptRequest(
    case_id=guided_case.case_id,
    prediction="smaller excursion",
    changes=(ParameterValueDTO(key="H_s", value=6.0),),
)
result = run_portable_guided_attempt(request)
assert result.attempted_evaluation.first_swing.status == "stable"
"""
    second = """
from sincrolab.application import evaluate_transient, get_guided_case
config = get_guided_case("first-swing-event-evidence").baseline_config
evaluation = evaluate_transient(config)
assert evaluation.first_swing.status == "stable"
"""
    for example in (first, second):
        completed = subprocess.run(
            [sys.executable, "-c", example],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_changelog_closes_core_release_without_overclaiming() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_dates = re.findall(
        r"^## \[0\.1\.0-core\] - (.+)$", changelog, flags=re.MULTILINE
    )
    assert len(release_dates) == 1
    assert date.fromisoformat(release_dates[0]) == date(2026, 9, 5)
    assert not re.search(
        r"^## .*0\.1\.0-core.*Unreleased", changelog,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    assert "Portable application DTOs" in changelog
    assert "Temporal critical-clearing output is a bracket" in changelog
    assert "exact-CCT error bar" in changelog
    assert "PSS/E replacement" not in changelog


def test_citation_cff_has_valid_minimal_confirmed_metadata() -> None:
    content = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    top_level_keys = [
        match.group(1)
        for line in content.splitlines()
        if (match := re.match(r"^([a-z][a-z-]*):(?:\s|$)", line))
    ]
    assert len(top_level_keys) == len(set(top_level_keys))
    assert {
        "cff-version",
        "message",
        "title",
        "type",
        "version",
        "authors",
        "repository-code",
        "license",
        "abstract",
    } == set(top_level_keys)
    assert content.startswith("cff-version: 1.2.0\n")
    assert 'title: "SincroLab"' in content
    assert "type: software" in content
    assert 'version: "0.1.0-core"' in content
    assert '  - name: "SincroLab contributors"' in content
    assert (
        'repository-code: "https://github.com/giovanni-serrano/sincro-lab"'
        in content
    )
    for invented_field in ("doi:", "orcid:", "affiliation:", "date-released:"):
        assert invented_field not in content


def test_public_documents_contain_no_local_paths_or_personal_metadata() -> None:
    public = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "CHANGELOG.md", "CITATION.cff")
    ).lower()
    assert "c:\\users\\" not in public
    assert "/home/" not in public
    assert "timestamp" not in public
    assert "uuid" not in public
    assert "telemetry endpoint" not in public


def test_project_metadata_and_citation_versions_are_deliberate() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert project["project"]["version"] == "0.1.0"
    assert 'version: "0.1.0-core"' in citation
    capabilities = get_capabilities()
    assert capabilities.package_version == "0.1.0"
    assert capabilities.release_target == "v0.1.0-core"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`0.1.0` es la versión del paquete Python" in readme
    assert "`v0.1.0-core` es el identificador del release/tag Git del core" in readme


def test_sdist_build_keeps_public_sources_and_rejects_local_files(tmp_path: Path) -> None:
    """Inspect a real build without treating local Git excludes as packaging policy."""
    project = tmp_path / "checkout"
    project.mkdir()
    public_metadata = (
        "pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md",
        "CITATION.cff", ".gitignore", "uv.lock",
    )
    for name in public_metadata:
        shutil.copy2(ROOT / name, project / name)
    for name in ("src", "reference_cases", "tests", "web"):
        shutil.copytree(
            ROOT / name, project / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )

    local_paths = (
        ".audit/RELEASE_SENTINEL_PRIVATE.txt",
        "docs/PROGRESS.md",
        "docs/LEARNING_GUIDE.md",
        ".venv/pyvenv.cfg",
        "local-environment/Lib/site-packages/private_module.py",
        "local-notes.txt",
        "local-script.py",
        "src/sincrolab/local-environment/private_module.py",
        "src/sincrolab/application/private-notes.txt",
        "src/sincrolab/interfaces/desktop/private-notes.txt",
        "src/sincrolab/interfaces/desktop/local-environment/private_module.py",
        "reference_cases/local-backup.json.bak",
        "tests/local-output.json",
        "src/sincrolab/interfaces/web/private_module.py",
        "src/sincrolab/interfaces/web/local-environment/private_module.py",
        "web/private.js",
        "web/private.json",
        "web/local-environment/private_module.py",
        "web/H29_screenshot.png",
        "web/dist/private.json",
    )
    marker = "PRIVATE_" + "SDIST_SENTINEL"
    for name in local_paths:
        sentinel = project / name
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(marker, encoding="utf-8")
    git_info = project / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text(".audit/\ndocs/\n", encoding="utf-8")

    uv = shutil.which("uv")
    assert uv is not None, "The supported development/build workflow requires uv"
    completed = subprocess.run(
        [uv, "build", "--sdist", "--out-dir", str(tmp_path / "dist")],
        cwd=project, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    archives = tuple((tmp_path / "dist").glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        contents = {
            member.name.split("/", 1)[1]: archive.extractfile(member).read()
            for member in archive.getmembers() if member.isfile()
        }
    assert set(public_metadata) <= contents.keys()
    assert {
        "PKG-INFO",
        "src/sincrolab/__init__.py",
        "src/sincrolab/application/portable.py",
        "src/sincrolab/application/_h23_reference_projection.json",
        "src/sincrolab/interfaces/cli/main.py",
        "reference_cases/smib_v0_1_golden_cases.json",
        "tests/test_golden_cases.py",
        "tests/test_release_metadata.py",
    } <= contents.keys()
    desktop_sources = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "src/sincrolab/interfaces/desktop").glob("*.py")
    }
    assert desktop_sources
    assert desktop_sources <= contents.keys()
    assert {
        "src/sincrolab/interfaces/web/__init__.py",
        "src/sincrolab/interfaces/web/bridge.py",
        "web/index.html", "web/styles.css", "web/app.js", "web/plots.js",
        "web/runtime.js", "web/worker.js", "web/pyodide-config.js",
        "web/assemble.py", "tests/web_browser_check.py",
    } <= contents.keys()
    assert set(local_paths).isdisjoint(contents)
    assert all(marker.encode() not in content for content in contents.values())
    assert not any(
        part in {".audit", ".venv", "local-environment", "__pycache__"}
        for name in contents for part in Path(name).parts
    )
