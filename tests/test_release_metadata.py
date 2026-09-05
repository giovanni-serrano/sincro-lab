from pathlib import Path
import re
import subprocess
import sys
import tomllib


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
        "no incluye todavía GUI desktop ni web",
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


def test_changelog_describes_unreleased_core_without_overclaiming() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0-core] - Unreleased" in changelog
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
