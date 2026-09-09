"""Production asset boundary, reproducible assembly and adversarial packaging."""

import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile

import pytest

from sincrolab.application import portable


ROOT = Path(__file__).parents[1]
WEB = ROOT / "web"
spec = importlib.util.spec_from_file_location("assemble_web", WEB / "assemble.py")
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("src", "href"):
            if key in attrs and attrs[key].startswith("./"):
                self.refs.append(attrs[key][2:])
        if "id" in attrs:
            self.ids.append(attrs["id"])


def test_production_assets_resolve_and_have_accessible_loading_shell():
    parser = Assets()
    html = (WEB / "index.html").read_text(encoding="utf-8")
    parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))
    assert all((WEB / name).is_file() for name in parser.refs)
    assert {"app.js", "styles.css"} <= set(parser.refs)
    assert 'lang="es"' in html and 'role="alert"' in html and 'role="status"' in html
    assert "disabled" in html and "viewport" in html
    for path in WEB.glob("*.js"):
        source = path.read_text(encoding="utf-8")
        for name in re.findall(r'(?:from|import)\s*[\(]?\s*["\'](\./[^"\']+)["\']', source):
            assert (WEB / name).is_file(), (path.name, name)


def test_exact_pyodide_no_floating_cdn_or_tracker():
    config = (WEB / "pyodide-config.js").read_text(encoding="utf-8")
    assert re.search(r'PYODIDE_VERSION\s*=\s*"\d+\.\d+\.\d+"', config)
    assert '"0.27.7"' in config
    assets = "\n".join(assembly.asset_path(name, ROOT).read_text(encoding="utf-8") for name in assembly.ASSETS)
    for forbidden in ("latest", "google-analytics", "sentry", "sendBeacon", "XMLHttpRequest", "WebSocket", "localStorage", "indexedDB", "randomUUID"):
        assert forbidden.lower() not in assets.lower()
    assert set(re.findall(r'https://([^/\s"`]+)', assets)) == {"cdn.jsdelivr.net"}
    assert 'method: "POST"' not in assets


def test_frontend_contains_no_parallel_cases_answers_or_science():
    source = "\n".join(assembly.asset_path(name, ROOT).read_text(encoding="utf-8") for name in assembly.ASSETS)
    for summary in portable.list_guided_cases():
        case = portable.get_guided_case(summary.case_id)
        assert case.case_id not in source
        assert case.context not in source
        assert case.prediction_prompt not in source
        for hint in portable.get_guided_hints(case.case_id, case.hints_available).hints:
            assert hint not in source
        for question in case.conceptual_questions:
            assert question.prompt not in source
    for forbidden in ("correct_option_id", "expected_observations", "Math.sin", "Math.cos", "Math.asin", "Math.PI", "cct_exact", "cct_estimate", "solve_ivp", "classical_rk4", "swing_rhs", "Pm_pu -", "2 * H", "max_delta_rad ="):
        assert forbidden not in source
    worker = (WEB / "worker.js").read_text(encoding="utf-8")
    assert 'loadPackage(["numpy", "micropip"])' in worker
    assert "deps=False" in worker and "scipy" not in worker.lower()
    assert "SHA-256" in worker and "wheel_sha256" in worker
    assert "from sincrolab.interfaces.web.bridge import dispatch_json" in worker
    assert not re.search(r'import\s+sincrolab\.(models|analysis|numerical|simulation)', source)


def test_ui_has_prediction_invalidation_ondemand_calls_and_explicit_errors():
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'session.prediction = ""' in source
    assert 'prediction_options.includes(session.prediction)' in source
    assert 'runtime.call("guided_hints"' in source and 'runtime.call("guided_solution"' in source
    for state in ("loading_pyodide", "loading_wheel", "ready", "running", "error"):
        assert state in source
    for failure in ("pyodide_bootstrap", "wheel_load", "sincrolab_import", "invalid_input", "portable_error", "unexpected"):
        assert failure in source
    assert "@media(max-width:" in (WEB / "styles.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def distribution(tmp_path_factory):
    output = tmp_path_factory.mktemp("web-distribution")
    build = subprocess.run([shutil.which("uv"), "build", "--out-dir", str(output)], cwd=ROOT, text=True, capture_output=True)
    assert build.returncode == 0, build.stdout + build.stderr
    return output


def test_sdist_carries_explicit_assets_and_wheel_carries_only_python(distribution):
    with tarfile.open(next(distribution.glob("*.tar.gz"))) as archive:
        names = {member.name.split("/",1)[1] for member in archive.getmembers() if member.isfile()}
    assert {f"web/{name}" for name in (*assembly.ASSETS, "assemble.py") if name not in assembly.SHARED_ASSETS} <= names
    assert {f"src/sincrolab/interfaces/assets/{name}" for name in assembly.SHARED_ASSETS} <= names
    assert "src/sincrolab/interfaces/web/bridge.py" in names
    with zipfile.ZipFile(next(distribution.glob("*.whl"))) as archive:
        names = set(archive.namelist())
    assert "sincrolab/interfaces/web/bridge.py" in names
    assert not any(name.startswith("web/") or ".audit" in name for name in names)


def test_assembly_is_deterministic_and_wheel_identity_is_exact(distribution, tmp_path):
    wheel = next(distribution.glob("*.whl"))
    site = tmp_path / "site"
    first = assembly.assemble(wheel, site)
    before = {path.name:path.read_bytes() for path in site.iterdir()}
    assert assembly.assemble(wheel, site) == first
    assert before == {path.name:path.read_bytes() for path in site.iterdir()}
    assert set(before) == {*assembly.ASSETS, wheel.name, "manifest.json"}
    assert first["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert json.loads((site / "manifest.json").read_text()) == first
    assert "case_id" not in json.dumps(first)
    assert str(ROOT) not in json.dumps(first)


def test_assembly_rejects_stale_wheel_and_unrelated_output(distribution, tmp_path):
    wheel = next(distribution.glob("*.whl"))
    checkout = tmp_path / "checkout"
    shutil.copytree(ROOT / "src", checkout / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(WEB, checkout / "web", ignore=shutil.ignore_patterns("__pycache__"))
    bridge = checkout / "src/sincrolab/interfaces/web/bridge.py"
    bridge.write_text(bridge.read_text(encoding="utf-8") + "\n# Changed source\n", encoding="utf-8")
    with pytest.raises(ValueError,match="does not match"):
        assembly.assemble(wheel,tmp_path / "stale",root=checkout)
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "private.txt"
    sentinel.write_text("preserve")
    with pytest.raises(ValueError,match="unrelated"):
        assembly.assemble(wheel,output)
    assert sentinel.read_text() == "preserve"
    with pytest.raises(ValueError,match="separate"):
        assembly.assemble(wheel,WEB)
