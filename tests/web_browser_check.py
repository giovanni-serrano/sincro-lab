"""Real HTTP/Pyodide gate using an existing Chrome and optional Playwright.

Run: uv run --with playwright==1.58.0 python tests/web_browser_check.py
No browser binaries, JS packages or production test endpoints are required.
Worker instrumentation observes messages without replacing computations.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
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


def select_topic(page, topic_id):
    """Use the navigation control available at the current viewport."""
    if page.locator(".topic-picker").is_visible():
        page.locator("#theory-topics").select_option(topic_id)
    elif topic_id == "glossary":
        page.locator(".topic-groups").get_by_role("button", name="Glosario →", exact=True).click()
    else:
        page.locator(f"#topic-nav-{topic_id}").click()


def verify_topic_navigation(page):
    """The grouped index and compact picker are mutually exclusive at 1100px."""
    original_viewport = page.viewport_size
    observations = []
    try:
        for width in (1280, 1101, 1100, 820, 390):
            page.set_viewport_size({"width": width, "height": 900})
            groups = page.locator(".topic-groups")
            picker = page.locator(".topic-picker")
            assert groups.is_visible() == (width > 1100), width
            assert picker.is_visible() == (width <= 1100), width
            assert groups.locator("button[id^=topic-nav-]").count() == 14
            assert picker.locator("optgroup option").count() == 14
            select_topic(page, "smib")
            assert page.locator("#theory-topics").input_value() == "smib"
            observations.append({"width": width,
                "groups_visible": groups.is_visible(),
                "picker_visible": picker.is_visible(),
                "groups_display": groups.evaluate("node => getComputedStyle(node).display"),
                "picker_display": picker.evaluate("node => getComputedStyle(node).display")})
    finally:
        page.set_viewport_size(original_viewport)
    return observations


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
            page.locator(f'#prediction input[value="{request.prediction}"]').check()
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
        shared = portable.get_learning_content().to_dict()
        actual_content = page.evaluate("window.__h29Messages.find(x=>x.type==='result' && x.operation==='learning_content')?.data")
        # Request IDs provide the operation provenance of each result message.
        if actual_content is None:
            actual_content = page.evaluate("""() => {
                const request = window.__h29Requests.find(x=>x.operation==='learning_content');
                return window.__h29Messages.find(x=>x.type==='result' && x.id===request.id).data;
            }""")
        check(actual_content, shared, "shared learning content")
        capture("HOME")
        page.locator("#home-nav").click()
        assert page.locator(".case-card button").evaluate_all("nodes=>nodes.map(x=>x.id)") == [
            "case-" + item["case_id"] for item in shared["cases"]
        ]
        page.locator("#learn-nav").click()
        evidence["topic_navigation"] = verify_topic_navigation(page)
        for topic in shared["topics"]:
            select_topic(page, topic["topic_id"])
            assert topic["learning_objective"] in page.locator("#view").inner_text()
            blocks = page.locator("[data-block-kind]")
            assert blocks.evaluate_all("nodes => nodes.map(x => x.dataset.blockKind)") == [block["kind"] for block in topic["blocks"]]
            assert blocks.locator("p").all_text_contents() == [block["text"] for block in topic["blocks"]]
            assert page.locator("[data-block-kind]:visible").count() == 1
            for block_index, block in enumerate(topic["blocks"]):
                visible_block = page.locator("[data-block-kind]:visible")
                assert visible_block.get_attribute("data-block-kind") == block["kind"]
                assert block["text"] in visible_block.inner_text()
                if topic["topic_id"] in ("swing-equation", "inertia"):
                    assert page.locator('[data-diagram="causal-chain"]').is_visible() == (block["kind"] == "equation")
                if block_index + 1 < len(topic["blocks"]):
                    page.locator("#lesson-continue").click()
            assert page.locator("#lesson-continue").is_hidden()
            page.locator("#lesson-show-all").click()
            assert page.locator("[data-block-kind]:visible").count() == len(topic["blocks"])
            page.locator("#lesson-show-all").click()
            assert page.locator("[data-block-kind]:visible").count() == 1
        for index, topic in enumerate(shared["topics"]):
            for key in topic["prerequisite_topic_ids"]:
                select_topic(page, topic["topic_id"])
                page.locator(f"#theory-topic-{key}").click()
                assert page.locator("#theory-topics").input_value() == key
            for key in topic["case_ids"]:
                page.locator("#learn-nav").click()
                select_topic(page, topic["topic_id"])
                page.locator(f"#theory-case-{key}").click()
                ready()
                assert not page.locator(".result-status").count()
                assert page.locator("#phase-2").is_disabled()
                expected_case = portable.get_guided_case(key)
                assert page.locator("#view h1").inner_text() == expected_case.title
                page.locator("#learn-nav").click()
            select_topic(page, topic["topic_id"])
            if index + 1 < len(shared["topics"]):
                page.locator("#theory-next").click()
                assert page.locator("#theory-topics").input_value() == shared["topics"][index + 1]["topic_id"]
        operations = page.evaluate("window.__h29Requests.map(x=>x.operation)")
        assert not {"guided_run", "guided_hints", "guided_solution"}.intersection(operations)
        evidence["steps"].append("all structured topics, prerequisites and experiment links without execution")
        page.locator("#lesson-show-all").click()
        capture("LEARN_LIMITATIONS")
        select_topic(page, "swing-equation")
        page.locator("#lesson-show-all").click()
        capture("LEARN_EQUATIONS")
        select_topic(page, "glossary")
        for term in shared["glossary"]:
            assert term["description"] in page.locator("#view").inner_text()
        capture("GLOSSARY")
        page.locator("#home-nav").click()
        capture("HOME")
        capture("RUNTIME_READY")
        requests = guided_requests()
        requests = [replace(request, changes=(portable.ParameterValueDTO("H_s", 5.0),))
                    if request.case_id == "controlled-inertia-effect" and not request.changes
                    else request for request in requests]
        for request in requests[:3]:
            page.locator(f"#case-{request.case_id}").click()
            ready()
            case = portable.get_guided_case(request.case_id)
            check(result(),case.to_dict(),f"metadata:{request.case_id}")
            outgoing = page.evaluate("window.__h29Requests.map(x=>x.operation)")
            assert "guided_solution" not in outgoing and "guided_hints" not in outgoing
            assert page.locator("#phase-4").is_disabled()
            assert not page.locator(".result-status").count()
            if request.case_id == "controlled-inertia-effect":
                capture("OBSERVE")
                page.get_by_text("Parámetros de la configuración inicial", exact=True).click()
                advanced = page.get_by_text("Detalles avanzados · configuración completa", exact=True).locator("..")
                assert not advanced.locator("table").is_visible()
                advanced.locator("summary").click()
                assert advanced.locator("table").is_visible()
                for key in ("D_pu", "f_base_hz", "dt_s"):
                    metadata = next(item for item in shared["quantities"] if item["key"] == key)
                    assert f"{metadata['label']} · {metadata['symbol']} ({metadata['unit']})" in advanced.inner_text()
                    assert metadata["description"] in advanced.inner_text()
                capture("ADVANCED")
                advanced.locator("summary").click()
            preparation = next(item for item in shared["cases"] if item["case_id"] == request.case_id)
            for key in ("remember", "observe", "experimental_question", "prediction_guidance"):
                assert preparation[key] in page.locator("#case-preparation").inner_text()
            page.locator("#begin-prediction").click()
            assert page.locator("#run-guided").is_disabled()
            assert page.locator("#run-guided").is_disabled()
            before = page.evaluate("window.__h29Requests.length")
            page.locator("#run-guided").evaluate("button=>button.click()")
            assert page.evaluate("window.__h29Requests.length") == before
            for key in preparation["topic_ids"]:
                page.locator("#case-preparation summary").click()
                page.locator(f"#review-{key}").click()
                assert page.locator("#theory-topics").input_value() == key
                page.locator("#theory-return-case").click()
                assert page.locator("#run-guided").is_disabled()
            if case.kind == "inertia_effect":
                page.locator(f'#prediction input[value="{request.prediction}"]').check()
                assert page.locator("#run-guided").is_disabled()
                page.locator("#prediction-intervention input").fill("5")
                assert page.locator("#prediction input:checked").count() == 0
                assert "Se ejecutará la configuración inicial del caso." not in page.locator("#view").inner_text()
            page.locator(f'#prediction input[value="{request.prediction}"]').check()
            page.locator("#case-preparation summary").click()
            page.locator(f"#review-{preparation['topic_ids'][0]}").click()
            page.locator("#theory-return-case").click()
            assert page.locator("#prediction input:checked").get_attribute("value") == request.prediction
            if request.case_id == "controlled-inertia-effect": capture("PREDICT")
            baseline = run_guided(request)
            if request.case_id == "controlled-inertia-effect":
                assert baseline["changed_parameters"][0]["key"] == "H_s"
                assert baseline["changed_parameters"][0]["attempted_value"] != baseline["changed_parameters"][0]["baseline_value"]
                assert baseline["debrief_summary"] in page.locator("#inertia-confrontation").inner_text()
                assert page.locator("#inertia-confrontation tbody tr").count() == 2
                capture("RESULT")
                page.locator("#phase-3").click()
                assert page.locator(".editor input").count() == 1
                page.locator("#input-H_s").fill("6")
                page.locator("#apply-changes").click()
                assert page.locator("#run-guided").is_disabled()
                attempt = run_guided(requests[-1])
                assert attempt["baseline_evaluation"] == baseline["baseline_evaluation"]
                capture("COMPARE")
                page.locator("#phase-3").click()
                assert page.locator("#input-H_s").input_value() == "6"
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
        page.locator("#begin-prediction").click()
        page.locator("#prediction-intervention input").fill("5")
        run_guided(requests[1])
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
            assert page.locator(".result-status").text_content() == next(item.label for item in portable.get_learning_content().meanings if item.key == expected["first_swing"]["status"])
            capture("FREE_" + next(item.label for item in portable.get_learning_content().meanings if item.key == expected["first_swing"]["status"]))
        assert evidence["console_errors"] == [] and evidence["page_errors"] == []
        evidence["clean_console_before_deliberate_errors"] = True
        # A real domain rejection must leave the previous completed result intact.
        page.locator("#input-dt_s").fill("-1")
        page.locator("#run-free").click()
        page.wait_for_function("document.querySelector('#error').hidden === false")
        assert "Traceback" not in page.locator("#error").inner_text()
        assert page.locator(".result-status").text_content() == "No concluyente"
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
