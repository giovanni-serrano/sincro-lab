"""Real Chrome/Pyodide gate for the introductory experiment and its original samples.

Run after build/assembly using the same optional Playwright environment as
web_browser_check.py. Evidence stays in the selected local audit directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from sincrolab.application import portable
from test_transient_lab import assert_blind_lab_discovery
from web_browser_check import INSTRUMENT, equivalent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8769")
    parser.add_argument("--output", type=Path, default=Path(".audit/H33/browser"))
    args = parser.parse_args()
    assert args.url.startswith(("http://127.0.0.1:", "http://localhost:"))
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {"steps": [], "screenshots": {}, "console_errors": [], "page_errors": [],
                "requests": [], "viewports": [], "float_values_compared": 0,
                "max_absolute_float_difference": 0.0}
    with sync_playwright() as automation:
        browser = automation.chromium.launch(channel="chrome", headless=True)
        evidence["browser"] = browser.version
        for width in (1280, 820, 390):
            context = browser.new_context(viewport={"width": width, "height": 844},
                                          reduced_motion="reduce")
            context.add_init_script(INSTRUMENT)
            context.on("request", lambda req: evidence["requests"].append({
                "method": req.method, "url": req.url, "has_body": req.post_data is not None}))
            page = context.new_page()
            page.on("console", lambda msg: evidence["console_errors"].append(msg.text)
                    if msg.type == "error" else None)
            page.on("pageerror", lambda err: evidence["page_errors"].append(str(err)))

            def ready():
                page.wait_for_function("document.querySelector('#runtime-status').dataset.state === 'ready' && document.querySelector('#view').getAttribute('aria-busy') === 'false'", timeout=180000)

            def capture(name, selector=None, full=False):
                path = args.output / f"{width}_{name}.png"
                if selector:
                    page.locator(selector).screenshot(path=str(path))
                else:
                    page.screenshot(path=str(path), full_page=full)
                evidence["screenshots"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, name)
                return path.name

            def check(text):
                evidence["steps"].append(f"{width}: {text}")
                print("PASS", width, text, flush=True)

            def result(operation):
                return page.evaluate("""operation => {
                    const request = window.__h29Requests.filter(x=>x.operation===operation).at(-1);
                    return window.__h29Messages.find(x=>x.type==='result' && x.id===request.id).data;
                }""", operation)

            def scrub(index):
                page.locator("#lab-scrub").evaluate("""(input, value) => {
                    input.value = String(value); input.dispatchEvent(new Event('input', {bubbles:true}));
                }""", index)
                assert page.locator("#transient-lab").get_attribute("data-sample-index") == str(index)

            def execute(prediction, index):
                page.locator(f'#lab-prediction input[value="{prediction}"]').check()
                assert page.locator("#lab-run").is_enabled()
                page.locator("#lab-run").click()
                ready()
                data = result("phenomenon_run")
                expected = portable.run_phenomenon(index, prediction)
                equivalent(data, expected, evidence, f"{width}:run:{index}")
                if page.locator("#lab-play").inner_text() == "Pausar":
                    page.wait_for_function("Number(document.querySelector('#transient-lab').dataset.sampleIndex)>0")
                    page.locator("#lab-play").click()
                paused = page.locator("#lab-time").get_attribute("data-time-s")
                page.wait_for_timeout(80)
                assert page.locator("#lab-time").get_attribute("data-time-s") == paused
                page.locator("#lab-reset").click()
                assert page.locator("#lab-time").get_attribute("data-time-s") == "0"
                return data

            def verify_plot(runs, mode):
                plot = page.locator("#lab-graph svg")
                metadata = plot.evaluate("""svg => ({
                    start:Number(svg.dataset.startS), end:Number(svg.dataset.endS),
                    min:Number(svg.dataset.minAngleDeg), max:Number(svg.dataset.maxAngleDeg),
                    width:svg.viewBox.baseVal.width, mode:svg.dataset.mode
                })""")
                assert metadata["mode"] == mode
                for label, response in runs.items():
                    run = response["run"]
                    curve = page.locator(f'[data-curve-run="{label}"]')
                    points = curve.evaluate("line=>Array.from(line.points,p=>[p.x,p.y])")
                    count = int(curve.get_attribute("data-sample-count"))
                    assert len(points) == count
                    expected_count = len(run["angle_deg"]) if mode == "full" else max(
                        item["lesson"]["first_swing_end_index"] for item in runs.values()) + 1
                    assert count == expected_count
                    # SVGPointList stores float32 presentation coordinates. The
                    # original float64 source arrays are separately compared above.
                    for i, (x, y) in enumerate(points):
                        t = run["evaluation"]["trajectory"]["time_s"][i]
                        angle = run["angle_deg"][i]
                        expected_x = 58 + (t-metadata["start"])/(metadata["end"]-metadata["start"])*(metadata["width"]-72)
                        expected_y = 210-(angle-metadata["min"])/(metadata["max"]-metadata["min"])*150
                        assert abs(x-expected_x) < 0.0001 and abs(y-expected_y) < 0.0001
                assert "Tiempo (s)" in plot.text_content() and "(°)" in plot.text_content()
                return metadata

            page.goto(args.url)
            ready()
            evidence["runtime"] = json.loads(page.locator("#runtime-identity").text_content())
            assert evidence["runtime"]["pyodide"] == "0.27.7"
            assert page.locator(".home-actions .primary").count() == 1
            capture("01_entry", full=True)
            page.locator("#open-transient-lab").click()
            ready()
            discovery = result("transient_lab")
            assert_blind_lab_discovery(discovery)
            assert page.evaluate("window.__h29Requests.every(x=>!['phenomenon_run','transient_lab_run'].includes(x.operation))")
            assert page.locator("#lab-run").is_disabled()
            assert page.locator("#lab-graph").is_hidden()
            assert page.locator("#lab-lesson").is_hidden()
            assert page.locator("#lab-prediction input:checked").count() == 0
            visible = page.locator("#transient-lab").inner_text()
            for text in ("STABLE", "UNSTABLE", "Pa =", "dδ/dt", "d(Δω)/dt", "La separación deja"):
                assert text not in visible
            page.evaluate("window.scrollTo(0,0)")
            initial_run_y = page.locator("#lab-run").bounding_box()["y"]
            capture("02_phenomenon_before_prediction", full=True)
            page.locator('#lab-prediction input[value="lose"]').check()
            capture("03_prediction_before_reveal", ".lab-decisions")
            assert page.locator("#lab-result").inner_text() == ""
            a = execute("lose", 0)
            assert "difiere" in page.locator("#lab-result").inner_text()
            run_box = page.locator("#lab-run").bounding_box()
            result_box = page.locator("#lab-result").bounding_box()
            action_result_gap = result_box["y"] - (run_box["y"] + run_box["height"])
            assert action_result_gap < 48
            capture("04_run_result", ".lab-decisions")
            page.locator("#lab-result details summary").click()
            capture("05_prediction_outcome_evidence", ".lab-decisions")
            scrub(30)
            assert page.locator(".lab-system").get_attribute("data-network-state") == "fault"
            scrub(40)
            assert page.locator(".lab-system").get_attribute("data-network-state") == "postfault"
            check("Blind discovery, confirmed prediction, mismatch confronted, original event states")
            page.locator("#lab-longer").click()
            handle = page.locator("#lab-clearing-handle")
            page.locator('#lab-prediction input[value="maintain"]').check()
            handle.focus()
            handle.press("ArrowLeft")
            assert page.locator("#lab-prediction input:checked").count() == 0
            assert page.locator("#lab-run").is_disabled()
            handle.press("Home")
            page.locator('#lab-prediction input[value="maintain"]').check()
            assert page.locator("#lab-run").is_disabled()  # A versus A is not an experiment.
            handle.scroll_into_view_if_needed()
            box = handle.bounding_box()
            rail = page.locator(".lab-edit-layer").bounding_box()
            page.mouse.move(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
            page.mouse.down()
            page.mouse.move(rail["x"]+rail["width"]+40, box["y"]+box["height"]/2, steps=12)
            page.mouse.up()
            assert page.locator("#lab-prediction input:checked").count() == 0
            assert float(handle.get_attribute("aria-valuenow")) == 0.25
            handle.press("End")
            b = execute("maintain", 30)
            assert page.locator("#transient-lab").get_attribute("data-comparing") == "true"
            assert "difiere" in page.locator('#lab-result [data-run="B"]').inner_text()
            scrub(40)
            angles = page.locator("[data-angle-deg]").evaluate_all("nodes=>nodes.map(n=>Number(n.dataset.angleDeg))")
            assert abs(angles[0]-angles[1]) < 1e-12
            assert page.locator(".lab-system").evaluate_all("nodes=>nodes.map(n=>n.dataset.networkState)") == ["postfault", "fault"]
            scrub(41)
            angles = page.locator("[data-angle-deg]").evaluate_all("nodes=>nodes.map(n=>Number(n.dataset.angleDeg))")
            assert angles[0] < angles[1]
            scrub(100)
            first_metadata = verify_plot({"A": a, "B": b}, "first")
            capture("06_first_swing", "#lab-graph")
            page.locator("#lab-full-view").click()
            full_metadata = verify_plot({"A": a, "B": b}, "full")
            assert full_metadata["end"] == 5
            scrub(1000)
            assert b["run"]["relative_turns"][-1] > 0
            capture("07_full_trajectory", "#lab-graph")
            page.locator("#lab-first-view").click()
            assert page.locator("#lab-cursor-note").is_visible()
            assert page.locator("[data-plot-run]").count() == 0
            scrub(40)
            check("Common scale, every rendered point checked, full original trajectory and explicit partial cursor")
            page.locator("#lab-reveal-cause").click()
            for index, stage in enumerate(b["lesson"]["stages"], start=1):
                assert page.locator("#lab-lesson").get_attribute("data-stage") == stage["id"]
                assert stage["text"] in page.locator("#lab-lesson").inner_text()
                if index < 6:
                    assert "dδ/dt" not in page.locator("#lab-lesson").inner_text()
                    assert page.locator("#lab-transfer").is_hidden()
                capture(f"08_stage_{index}", "#lab-lesson")
                if index < 6:
                    page.locator("#lab-next-explanation").click()
            # The three views must point at the same original sample.
            for index in (20, 40, 41, 70, 100):
                scrub(index)
                for label, source in (("A", a), ("B", b)):
                    expected_time = source["run"]["evaluation"]["trajectory"]["time_s"][index]
                    for selector in (f'[data-run="{label}"][data-angle-deg]', f'[data-plot-run="{label}"]', f'.lab-balance[data-run="{label}"]'):
                        assert float(page.locator(selector).get_attribute("data-time-s")) == expected_time
            page.locator("#lab-play").click()
            page.locator("#lab-theory").click()
            assert page.locator("#theory-topics").input_value() == "swing-equation"
            page.locator("#theory-return-lab").click()
            ready()
            assert page.locator("#lab-play").inner_text() == "Reproducir"
            check("Six ordered stages, damped equation last, exact sample linkage and theory return")
            previous_requests = page.evaluate("window.__h29Requests.filter(x=>x.operation==='phenomenon_run').length")
            page.locator("#lab-transfer").click()
            ready()
            draft = result("phenomenon_transfer")
            assert draft["choice_index"] not in (0, 30)
            assert page.evaluate("window.__h29Requests.filter(x=>x.operation==='phenomenon_run').length") == previous_requests
            assert page.locator("#lab-run").is_disabled()
            assert page.locator("#lab-result").inner_text() == ""
            assert page.locator("#lab-graph").is_hidden()
            assert page.locator("#lab-lesson").is_hidden()
            capture("09_transfer_before_prediction", full=True)
            c = execute("unsure", draft["choice_index"])
            assert c["run"]["evaluation"]["configuration"]["network"]["t_clear_s"] not in (0.2, 0.35)
            assert "evidencia" in page.locator('#lab-result [data-run="C"]').inner_text()
            page.locator('#lab-result [data-run="C"] details summary').click()
            capture("10_transfer_result_evidence", ".lab-decisions")
            verify_plot({"A": a, "C": c}, "first")
            capture("11_transfer_graph", "#lab-graph")
            assert page.locator(".lab-closing").is_visible()
            assert page.evaluate("async()=>{const {sampleIndex}=await import('./transient-lab.js'); return [-1,0,.006,.009,10].map(t=>sampleIndex([0,.005,.01],t));}") == [0,0,1,2,2]
            check("Unseen transfer, renewed prediction, no premature data, post-run evidence and reflection")
            evidence["viewports"].append({
                "width": width, "height": 844, "initial_run_y": initial_run_y,
                "action_result_gap_px": action_result_gap,
                "first_view": first_metadata, "full_view": full_metadata,
                "transfer_choice_index": draft["choice_index"]
            })
            context.close()
        assert not evidence["console_errors"] and not evidence["page_errors"]
        assert all(req["method"] == "GET" and not req["has_body"] for req in evidence["requests"])
        assert all(req["url"].startswith((args.url, "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/")) for req in evidence["requests"])
        browser.close()
    evidence["status"] = "PASS"
    (args.output / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
