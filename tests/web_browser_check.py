"""Real HTTP/Pyodide gate using an existing Chrome and optional Playwright.

Run: uv run --with playwright==1.58.0 python tests/web_browser_check.py
No browser binaries, JS packages or production test endpoints are required.
Worker instrumentation observes messages without replacing computations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from playwright.sync_api import sync_playwright

from sincrolab.application import portable
from test_web_parity import free_configs, guided_requests


INSTRUMENT = """
window.__h29Messages = [];
window.__h29Requests = [];
const OriginalWorker = window.Worker;
window.Worker = class extends OriginalWorker {
  constructor(...args) {
    super(...args);
    this.addEventListener('message', ({data}) => window.__h29Messages.push(data));
  }
  postMessage(data, ...args) {
    window.__h29Requests.push(structuredClone(data));
    super.postMessage(data, ...args);
  }
};
"""


def equivalent(actual, expected, statistics, path="root"):
    """Cross-runtime float64 comparison; categorical and textual fields exact.

    Absolute 1e-12 and relative 1e-11 cover platform libm/NumPy roundoff for
    these retained cases only. They are parity tolerances, not physical errors
    or a replacement for H22's independent dt convergence evidence.
    """
    if isinstance(expected, float):
        assert type(actual) in (int,float) and math.isfinite(actual), path
        difference = abs(actual - expected)
        statistics["max_absolute_float_difference"] = max(statistics["max_absolute_float_difference"], difference)
        statistics["float_values_compared"] += 1
        assert math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-12), (path,actual,expected)
    elif isinstance(expected, dict):
        assert isinstance(actual,dict) and set(actual) == set(expected), path
        for key in expected:
            equivalent(actual[key],expected[key],statistics,f"{path}.{key}")
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual) == len(expected), path
        for index,(left,right) in enumerate(zip(actual,expected,strict=True)):
            equivalent(left,right,statistics,f"{path}[{index}]")
    else:
        assert type(actual) is type(expected) and actual == expected, (path,actual,expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="http://127.0.0.1:8765")
    parser.add_argument("--output",type=Path,default=Path(".audit"))
    parser.add_argument("--channel",default="chrome")
    args = parser.parse_args()
    assert args.url.startswith(("http://127.0.0.1:","http://localhost:")), "Use local HTTP"
    args.output.mkdir(parents=True,exist_ok=True)
    evidence = {"url":args.url,"real_browser":True,"pyodide_real":True,"steps":[],
        "float_values_compared":0,"max_absolute_float_difference":0.0,"screenshots":{},"requests":[],"console_errors":[],"page_errors":[]}
    with sync_playwright() as automation:
        browser = automation.chromium.launch(channel=args.channel,headless=True)
        evidence["browser"] = {"channel":args.channel,"version":browser.version,"headless":True}
        context = browser.new_context(viewport={"width":1280,"height":900})
        context.add_init_script(INSTRUMENT)
        context.on("request",lambda req:evidence["requests"].append({"method":req.method,"url":req.url,"has_body":req.post_data is not None}))
        page = context.new_page()
        page.on("console",lambda msg:evidence["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror",lambda err:evidence["page_errors"].append(str(err)))

        def capture(name):
            path = args.output / f"H29_{name}.png"
            page.screenshot(path=str(path),full_page=True)
            evidence["screenshots"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

        def ready():
            page.wait_for_function("document.querySelector('#runtime-status').dataset.state === 'ready' && document.querySelector('#view').getAttribute('aria-busy') === 'false'",timeout=180000)

        def result():
            return page.evaluate("window.__h29Messages.filter(x=>x.type==='result' && x.ok).at(-1).data")

        def check(actual, expected, label):
            equivalent(actual,expected,evidence,label)
            evidence["steps"].append(label)
            print("PASS",label,flush=True)

        def run_guided(request):
            page.locator("#prediction").select_option(request.prediction)
            assert page.locator("#run-guided").is_enabled()
            page.locator("#run-guided").click()
            ready()
            actual = result()
            check(actual,portable.run_guided_attempt(request).to_dict(),f"guided:{request.case_id}:{len(request.changes)} changes")
            return actual

        page.goto(args.url)
        ready()
        assert not page.locator("#error").is_visible()
        identity = json.loads(page.locator("#runtime-identity").text_content())
        evidence["runtime_identity"] = identity
        manifest = context.request.get(f"{args.url}/manifest.json").json()
        wheel_bytes = context.request.get(f"{args.url}/{manifest['wheel']}").body()
        assert hashlib.sha256(wheel_bytes).hexdigest() == identity["wheel_sha256"] == manifest["wheel_sha256"]
        assert identity["pyodide"] == "0.27.7"
        check(identity["capabilities"],portable.get_capabilities().to_dict(),"runtime capabilities")
        check(result(),json.loads(portable.dumps_portable(portable.list_guided_cases())),"ordered catalog")
        capture("HOME")
        capture("RUNTIME_READY")
        requests = guided_requests()
        for request in requests[:3]:
            page.locator(f"#case-{request.case_id}").click()
            ready()
            case = portable.get_guided_case(request.case_id)
            check(result(),case.to_dict(),f"metadata:{request.case_id}")
            outgoing = page.evaluate("window.__h29Requests.map(x=>x.operation)")
            assert "guided_solution" not in outgoing and "guided_hints" not in outgoing
            assert page.locator("#phase-4").is_disabled()
            assert not page.locator(".result-status").count()
            if request.case_id == "controlled-inertia-effect": capture("OBSERVE")
            page.locator("#begin-prediction").click()
            assert page.locator("#run-guided").is_disabled()
            before = page.evaluate("window.__h29Requests.length")
            page.locator("#run-guided").evaluate("button=>button.click()")
            assert page.evaluate("window.__h29Requests.length") == before
            if request.case_id == "controlled-inertia-effect": capture("PREDICT")
            baseline = run_guided(request)
            if request.case_id == "controlled-inertia-effect":
                capture("RESULT")
                page.locator("#phase-3").click()
                assert page.locator(".editor input").count() == 1
                page.locator("#input-H_s").fill("6")
                page.locator("#apply-changes").click()
                assert page.locator("#run-guided").is_disabled()
                attempt = run_guided(requests[-1])
                assert attempt["baseline_evaluation"] == baseline["baseline_evaluation"]
                capture("COMPARE")
                page.locator("#phase-5").click()
                assert attempt["debrief_summary"] in page.locator("#view").inner_text()
                assert attempt["attempted_evaluation"]["explanation"]["summary"] in page.locator("#view").inner_text()
                capture("EXPLAIN")
            if request.case_id == "late-clearing-bracket":
                page.locator("#phase-5").click()
                assert page.locator("td[title=" + json.dumps(str(baseline["critical_clearing_bracket"]["stable_t_clear_s"])) + "]").count() >= 1
                capture("CCT")
            page.locator("#home-nav").click()

        page.locator("#case-controlled-inertia-effect").click(); ready()
        page.locator("#begin-prediction").click(); run_guided(requests[1])
        page.locator("#phase-3").click()
        page.locator("#input-H_s").fill("5.75")
        for count in (1,2):
            page.locator("#next-hint").click(); ready()
            check(result(),portable.get_guided_hints("controlled-inertia-effect",count).to_dict(),f"hint:{count}")
            assert page.locator("#input-H_s").input_value() == "5.75"
        page.locator("#reveal-solution").click(); ready()
        solution = portable.get_guided_solution("controlled-inertia-effect")
        check(result(),solution.to_dict(),"explicit solution")
        assert page.locator("#run-guided").is_disabled()
        capture("SOLUTION")
        solution_request = portable.GuidedAttemptRequest("controlled-inertia-effect",requests[1].prediction,
            changes=tuple(portable.ParameterValueDTO(x.key,x.value) for x in solution.settings),hints_revealed=2,reveal_solution=True)
        run_guided(solution_request)
        page.locator("#free-nav").click(); ready()
        for config in free_configs():
            for key,value in {"H_s":config.parameters.H_s,"t_clear_s":config.network.t_clear_s,"t_end_s":config.t_end_s,"dt_s":config.dt_s}.items():
                page.locator(f"#input-{key}").fill(str(value))
            page.locator("#run-free").click(); ready()
            expected = portable.evaluate_transient(config).to_dict()
            check(result(),expected,f"free:{expected['first_swing']['status']}")
            assert page.locator(".result-status").text_content() == expected["first_swing"]["status"].upper()
            capture("FREE_" + expected["first_swing"]["status"].upper())
        assert evidence["console_errors"] == [] and evidence["page_errors"] == []
        evidence["clean_console_before_deliberate_errors"] = True
        # A real domain rejection must leave the previous completed result intact.
        page.locator("#input-dt_s").fill("-1")
        page.locator("#run-free").click()
        page.wait_for_function("document.querySelector('#error').hidden === false")
        assert "Traceback" not in page.locator("#error").inner_text()
        assert page.locator(".result-status").text_content() == "INDETERMINATE"
        capture("INPUT_ERROR")
        page.locator("#input-dt_s").fill("0.005")
        page.locator("#run-free").click(); ready()
        page.set_viewport_size({"width":390,"height":844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        capture("MOBILE_FREE")
        page.locator("#home-nav").click()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        capture("MOBILE_HOME")
        page.locator("#case-controlled-inertia-effect").click(); ready()
        page.locator("#phase-4").click()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        capture("MOBILE_COMPARE")
        page.set_viewport_size({"width":820,"height":1000})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        capture("TABLET_COMPARE")
        assert all(item["method"] == "GET" and not item["has_body"] for item in evidence["requests"])
        assert all(item["url"].startswith((args.url, "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/")) for item in evidence["requests"])
        evidence["loading_states"] = page.evaluate("[...new Set(window.__h29Messages.filter(x=>x.type==='state').map(x=>x.state))]")
        assert {"loading_pyodide","loading_wheel","running","ready"} <= set(evidence["loading_states"])
        evidence["status"] = "PASS"
        (args.output / "H29_BROWSER.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding="utf-8")
        browser.close()
    print("PASS real-browser gate; evidence:",args.output / "H29_BROWSER.json",flush=True)


if __name__ == "__main__":
    main()
