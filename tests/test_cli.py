import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sincrolab.application import (
    GuidedAttemptRequest,
    ParameterValueDTO,
    reproduce_reference_case,
    run_portable_guided_attempt,
)
from sincrolab.interfaces.cli import main


def test_cli_module_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "sincrolab.interfaces.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "guided" in completed.stdout
    assert "reference" in completed.stdout


def test_cli_lists_guided_cases(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guided", "list"]) == 0
    output = capsys.readouterr().out
    assert "late-clearing-bracket: Efecto del tiempo de despeje" in output
    assert "controlled-inertia-effect: Efecto controlado de la inercia" in output
    assert "first-swing-event-evidence: Reconocer la estabilidad de primera oscilación" in output


def test_cli_inspects_guided_case_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guided", "show", "controlled-inertia-effect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["case_id"] == "controlled-inertia-effect"
    assert payload["editable_parameters"][0]["key"] == "H_s"
    assert "correct_option_id" not in json.dumps(payload)


def test_cli_runs_guided_attempt_and_matches_application_api(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "guided",
                "run",
                "controlled-inertia-effect",
                "--prediction",
                "smaller excursion",
                "--set",
                "H_s=6.0",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    expected = run_portable_guided_attempt(
        GuidedAttemptRequest(
            case_id="controlled-inertia-effect",
            prediction="smaller excursion",
            changes=(ParameterValueDTO("H_s", 6.0),),
        )
    )
    assert payload["attempted_evaluation"]["first_swing"]["status"] == (
        expected.attempted_evaluation.first_swing.status
    )
    assert payload["attempted_evaluation"]["first_swing"]["reason"] == (
        expected.attempted_evaluation.first_swing.reason
    )
    assert payload["scientific_comparison"]["attempted_max_delta_rad"] == (
        expected.scientific_comparison.attempted_max_delta_rad
    )
    assert payload["local_assessment"]["assessed"] is False


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "guided",
                "run",
                "controlled-inertia-effect",
                "--prediction",
                "invalid",
            ],
            "prediction",
        ),
        (
            [
                "guided",
                "run",
                "controlled-inertia-effect",
                "--prediction",
                "smaller excursion",
                "--set",
                "t_clear_s=0.2",
            ],
            "not editable",
        ),
        (
            [
                "guided",
                "run",
                "controlled-inertia-effect",
                "--prediction",
                "smaller excursion",
                "--set",
                "H_s=100",
            ],
            "editable bounds",
        ),
    ],
)
def test_cli_reports_guided_input_errors_cleanly(
    arguments: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(arguments) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert message in captured.err


def test_cli_rejects_incomplete_pre_post_assessment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "guided",
            "run",
            "controlled-inertia-effect",
            "--prediction",
            "smaller excursion",
            "--pre-answer",
            "accelerating_power=a",
        ]
    )
    assert code == 2
    assert "supplied together" in capsys.readouterr().err


def test_cli_preserves_complete_pre_post_score(
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [
        "guided",
        "run",
        "controlled-inertia-effect",
        "--prediction",
        "smaller excursion",
        "--pre-answer",
        "accelerating_power=a",
        "--pre-answer",
        "first_swing_evidence=b",
        "--post-answer",
        "accelerating_power=a",
        "--post-answer",
        "first_swing_evidence=b",
        "--json",
    ]
    assert main(arguments) == 0
    assessment = json.loads(capsys.readouterr().out)["local_assessment"]
    assert assessment["assessed"] is True
    assert assessment["pre_score"] == {
        "correct": 2,
        "schema_version": 1,
        "total": 2,
    }


def test_cli_reveals_hints_progressively_and_solution_explicitly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guided", "hints", "late-clearing-bracket", "--count", "1", "--json"]) == 0
    hint = json.loads(capsys.readouterr().out)
    assert len(hint["hints"]) == 1
    assert main(["guided", "solution", "late-clearing-bracket", "--json"]) == 0
    solution = json.loads(capsys.readouterr().out)
    assert solution["settings"][0]["key"] == "t_clear_s"
    assert "no un ajuste de protección" in solution["limitation"]


def test_cli_human_output_reveals_requested_hint_and_solution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guided", "hints", "late-clearing-bracket", "--count", "1"]) == 0
    hint_output = capsys.readouterr().out
    assert "Pista 1:" in hint_output
    assert "balance acelerante" in hint_output
    assert main(["guided", "solution", "late-clearing-bracket"]) == 0
    solution_output = capsys.readouterr().out
    assert "una solución pedagógica posible" in solution_output
    assert "Explicación:" in solution_output
    assert "Limitación:" in solution_output


def test_cli_lists_and_reproduces_reference_case(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["reference", "list"]) == 0
    assert "stable_transient" in capsys.readouterr().out
    assert main(["reference", "run", "stable_transient", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    expected = reproduce_reference_case("stable_transient")
    assert payload["verification_scope"] == expected.verification_scope
    assert payload["evaluation"]["first_swing"]["status"] == (
        expected.evaluation.first_swing.status
    )
    assert payload["evaluation"]["first_swing"]["reason"] == (
        expected.evaluation.first_swing.reason
    )
    assert payload["all_reported_observations_match_expected"] is True
    assert len(payload["observations"]) == len(expected.observations)


def test_cli_adversarial_output_states_resolution_limitation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "reference",
                "run",
                "adversarial_time_step",
                "--dt-s",
                "0.2",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluation"]["first_swing"]["status"] == "unstable"
    assert payload["verification_scope"] == (
        "selected_time_step_classification"
    )
    assert payload["observations"][0]["expected"]["evidence_type"] == (
        "ACCEPTED_REGRESSION"
    )
    assert payload["all_reported_observations_match_expected"] is True
    assert "trajectory-resolution sensitivity" in payload["limitation"]


def test_cli_writes_json_and_csv_exports(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "trajectory.csv"
    assert (
        main(
            [
                "reference",
                "run",
                "stable_transient",
                "--json-output",
                str(json_path),
                "--csv-output",
                str(csv_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["evaluation"]["first_swing"]["status"] == "stable"
    assert payload["all_reported_observations_match_expected"] is True
    assert csv_path.read_text(encoding="utf-8").splitlines()[0] == (
        "time_s,delta_rad,omega_dev_pu"
    )


def test_cli_rejects_query_only_reference_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["reference", "run", "scipy_cross_checked_transient"]) == 2
    assert "query-only" in capsys.readouterr().err


def test_cli_reports_unknown_case_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["guided", "show", "missing-case"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown guided case_id" in captured.err


def test_cli_reports_invalid_output_path_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "reference",
                "run",
                "stable_transient",
                "--json-output",
                str(tmp_path),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")


def test_cli_does_not_translate_runtime_invariant_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    cli_module = importlib.import_module("sincrolab.interfaces.cli.main")

    def raise_invariant_error(_args: object) -> object:
        raise RuntimeError("internal invariant failed")

    monkeypatch.setattr(cli_module, "_dispatch", raise_invariant_error)
    with pytest.raises(RuntimeError, match="internal invariant failed"):
        cli_module.main(["capabilities"])


def test_cli_adapter_contains_no_solver_or_classifier_implementation() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "src"
        / "sincrolab"
        / "interfaces"
        / "cli"
        / "main.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_import_roots = {
        "sincrolab.analysis",
        "sincrolab.models",
        "sincrolab.numerical",
        "sincrolab.simulation",
    }
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert imported.isdisjoint(forbidden_import_roots)
    assert {
        "classical_rk4",
        "explicit_euler",
        "assess_smib_first_swing",
        "simulate_smib_transient",
    }.isdisjoint(called_names)


def test_cli_emits_utf8_even_when_the_process_locale_requests_ascii():
    import os
    environment = dict(os.environ, PYTHONIOENCODING="ascii")
    completed = subprocess.run(
        [sys.executable, "-m", "sincrolab.interfaces.cli", "guided", "run",
         "controlled-inertia-effect", "--prediction", "smaller excursion",
         "--set", "H_s=6", "--json"],
        capture_output=True, env=environment,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8")
    result = json.loads(completed.stdout.decode("utf-8"))
    assert "3.5 → 6 s" in result["debrief_summary"]
    assert "Diagnóstico inicial" in result["debrief_summary"]


def test_cli_primary_guided_copy_uses_shared_spanish_labels(capsys):
    from sincrolab.interfaces.cli.main import build_parser

    help_text = build_parser().format_help()
    assert "casos guiados" in help_text
    assert "H25" not in help_text
    assert main(["guided", "show", "controlled-inertia-effect"]) == 0
    shown = capsys.readouterr().out
    assert "Inercia del generador" in shown
    assert "H_s" not in shown
    assert main(["guided", "run", "first-swing-event-evidence", "--prediction", "stable"]) == 0
    result = capsys.readouterr().out
    assert "Estable" in result
    assert "Reversión antes del cruce" in result
    assert "status=" not in result
