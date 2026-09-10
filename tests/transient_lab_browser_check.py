"""Local HTTP / real Chrome + Pyodide verification for H30-C.

Run with the same optional Playwright environment as web_browser_check.py.
All screenshots and JSON evidence stay in an explicitly selected local folder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from sincrolab.application import portable
from web_browser_check import INSTRUMENT, equivalent
from test_transient_lab import assert_blind_lab_discovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8767")
    parser.add_argument("--output", type=Path, default=Path(".audit/H30C/browser"))
    args = parser.parse_args()
    assert args.url.startswith(("http://127.0.0.1:", "http://localhost:"))
    args.output.mkdir(parents=True, exist_ok=True)
    lab = portable.get_transient_lab()
    evidence = {"steps":[], "screenshots":{}, "console_errors":[], "page_errors":[],
                "requests":[], "float_values_compared":0, "max_absolute_float_difference":0.0}
    with sync_playwright() as automation:
        browser = automation.chromium.launch(channel="chrome", headless=True)
        evidence["browser"] = browser.version
        context = browser.new_context(viewport={"width":1280, "height":800}, reduced_motion="reduce")
        context.add_init_script(INSTRUMENT)
        context.on("request",lambda req:evidence["requests"].append({"method":req.method,"url":req.url,"has_body":req.post_data is not None}))
        page = context.new_page()
        page.on("console",lambda msg:evidence["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror",lambda err:evidence["page_errors"].append(str(err)))

        def ready():
            page.wait_for_function("document.querySelector('#runtime-status').dataset.state === 'ready' && document.querySelector('#view').getAttribute('aria-busy') === 'false'",timeout=180000)

        def capture(name):
            page.evaluate("window.scrollTo(0,0)")
            path = args.output / f"{name}.png"
            page.screenshot(path=str(path),full_page=False)
            evidence["screenshots"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

        def check(label):
            evidence["steps"].append(label)
            print("PASS",label,flush=True)

        def scrub(index):
            control = page.locator("#lab-scrub")
            control.fill(str(index)); control.dispatch_event("input")
            assert page.locator("#transient-lab").get_attribute("data-sample-index") == str(index)

        def execute(prediction, index):
            page.locator(f'#lab-prediction input[value="{prediction}"]').check()
            assert page.locator("#lab-run").is_enabled()
            page.locator("#lab-run").click(); ready()
            actual = page.evaluate("window.__h29Messages.filter(x=>x.type==='result' && x.ok).at(-1).data")
            expected = portable.run_transient_lab(index,prediction).to_dict()
            equivalent(actual,expected,evidence,f"lab-run-{index}")
            assert page.locator("#lab-play").inner_text() == "Pausar"
            page.wait_for_function("Number(document.querySelector('#transient-lab').dataset.sampleIndex)>3")
            page.locator("#lab-play").click()
            assert page.locator("#lab-play").inner_text() == "Reproducir"
            before = page.locator("#lab-time").get_attribute("data-time-s")
            page.wait_for_timeout(120)
            assert page.locator("#lab-time").get_attribute("data-time-s") == before
            page.locator("#lab-reset").click()
            assert page.locator("#lab-time").get_attribute("data-time-s") == "0"
            return actual

        page.goto(args.url); ready()
        page.locator("#open-transient-lab").click(); ready()
        discovery = page.evaluate("""() => {
            const request = window.__h29Requests.find(x => x.operation === 'transient_lab');
            return window.__h29Messages.find(x => x.type === 'result' && x.id === request.id);
        }""")
        assert discovery["ok"]
        assert_blind_lab_discovery(discovery["data"])
        equivalent(discovery["data"], lab.to_dict(), evidence, "blind-lab-discovery")
        assert page.evaluate("window.__h29Requests.every(x => x.operation !== 'transient_lab_run')")
        assert page.locator("#lab-prediction input:checked").count() == 0
        evidence["discovery_before_prediction"] = discovery["data"]
        check("Real worker discovery payload contains no outcome associations before prediction")
        assert page.locator("#lab-clearing-handle").is_disabled()
        assert page.locator("#lab-run").is_disabled()
        assert page.locator("#lab-reveal-cause").is_hidden()
        assert page.locator("#lab-graph").is_hidden()
        visible = page.locator("#transient-lab").inner_text()
        for symbol in ("δ", "Δω", "Pm", "Pe", "Pa ="):
            assert not re.search(r"(?<!\w)" + re.escape(symbol) + r"(?!\w)", visible), symbol
        capture("01_initial_laptop")
        assert page.locator("#lab-run").bounding_box()["y"] < 800
        check("Initial discovery without formal variables or automatic simulation")
        a = execute("unsure",0)
        scrub(30); capture("02_a_fault")
        assert page.locator(".lab-system").get_attribute("data-network-state") == "fault"
        scrub(40)
        assert page.locator(".lab-system").get_attribute("data-network-state") == "postfault"
        scrub(1000)
        assert "Mantiene sincronismo" in page.locator("#lab-result").inner_text()
        assert page.locator("#lab-clearing-handle").is_enabled()
        check("Real stable run, event boundaries, play/pause/reset/scrub")

        handle = page.locator("#lab-clearing-handle")
        page.locator('#lab-prediction input[value="maintain"]').check()
        handle.focus(); handle.press("ArrowRight")
        assert not page.locator('#lab-prediction input[value="maintain"]').is_checked()
        assert page.locator("#lab-run").is_disabled()
        handle.press("Home"); handle.press("ArrowLeft")
        assert float(handle.get_attribute("aria-valuenow")) == lab.clearing_choices[0].fault_duration_s
        box = handle.bounding_box(); rail = page.locator(".lab-edit-layer").bounding_box()
        page.mouse.move(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
        page.mouse.down()
        page.mouse.move(rail["x"]+rail["width"]+40,box["y"]+box["height"]/2,steps=16)
        page.mouse.up()
        assert float(handle.get_attribute("aria-valuenow")) == lab.clearing_choices[-1].fault_duration_s
        assert "0.350 s" in page.locator("#lab-event-times").inner_text()
        capture("03_duration_dragged")
        check("Pointer drag and keyboard bounds; duration/absolute clearing; prediction invalidated")
        b = execute("lose",len(lab.clearing_choices)-1)
        scrub(1000)
        assert "Pierde sincronismo" in page.locator("#lab-result").inner_text()
        assert b["relative_turns"][-1] > 0
        capture("04_b_continuous_turns")
        check("Real unstable run, canonical outcome and continuous turn count")
        page.locator("#lab-compare").click()
        assert page.locator(".lab-event-row").count() == 2
        assert page.locator("#lab-clearing-handle").is_hidden()
        scrub(30)
        angles = page.locator("[data-angle-deg]").evaluate_all("nodes=>nodes.map(n=>Number(n.dataset.angleDeg))")
        assert abs(angles[0]-angles[1]) < 1e-12
        page.locator("#lab-inspect").click()
        assert page.locator("#lab-time").inner_text() == "0.200 s"
        assert page.locator(".lab-system").evaluate_all("nodes=>nodes.map(n=>n.dataset.networkState)") == ["postfault","fault"]
        capture("05_first_clearing")
        scrub(41)
        angles = page.locator("[data-angle-deg]").evaluate_all("nodes=>nodes.map(n=>Number(n.dataset.angleDeg))")
        assert angles[0] < angles[1]
        capture("06_divergence")
        check("Comparison shares timestamp and coincides before clearing; state/power diverge before position")

        style = page.add_style_tag(content=".lab-prompt,.lab-edit-note,.lab-outcome,.lab-scope {visibility:hidden !important}")
        for index in (30,40,60,120,300):
            scrub(index); capture(f"11_no_prose_{index}")
        style.evaluate("node=>node.remove()")
        page.locator("#lab-reveal-cause").click()
        assert page.locator(".lab-cause").is_visible()
        assert page.locator(".lab-formal").is_hidden()
        scrub(40); capture("07_cause")
        widths = page.locator(".lab-balance").evaluate_all("nodes=>nodes.map(n=>n.querySelector('.lab-power-rail i').style.width)")
        assert widths[0] == widths[1]
        page.locator("#lab-reveal-angle").click()
        assert "Ángulo del rotor — δ" in page.locator(".lab-view-heading").inner_text()
        assert "Pa = Pm − Pe" in page.locator(".lab-formal").inner_text()
        capture("08_formal_angle")
        page.locator("#lab-reveal-plot").click()
        for index in (0,20,40,41,70,132,300,1000):
            scrub(index)
            for label,source in [("A",a),("B",b)]:
                actual_time = float(page.locator(f'[data-run="{label}"][data-angle-deg]').get_attribute("data-time-s"))
                plot_time = float(page.locator(f'[data-plot-run="{label}"]').get_attribute("data-time-s"))
                power_time = float(page.locator(f'.lab-balance[data-run="{label}"]').get_attribute("data-time-s"))
                assert actual_time == plot_time == power_time == source["evaluation"]["trajectory"]["time_s"][index]
        scrub(70); capture("09_graph")
        plot_capture = args.output / "09_graph_detail.png"
        page.locator("#lab-graph").screenshot(path=str(plot_capture))
        evidence["screenshots"][plot_capture.name] = hashlib.sha256(plot_capture.read_bytes()).hexdigest()
        page.locator(".lab-cause").evaluate("node=>node.scrollTop=node.scrollHeight")
        formal_capture = args.output / "08_formal_detail.png"
        page.locator(".lab-cause").screenshot(path=str(formal_capture))
        evidence["screenshots"][formal_capture.name] = hashlib.sha256(formal_capture.read_bytes()).hexdigest()
        check("Cause, formal angle and plot progressively revealed; exact same source sample in every representation")

        for width in (820,390):
            page.set_viewport_size({"width":width,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            capture(f"10_responsive_{width}")
        page.set_viewport_size({"width":1280,"height":800})
        check("Laptop/mobile no overflow; captured no-prose event/divergence/turn review")
        # Navigation must stop playback and retain this workspace's session.
        page.locator("#lab-play").click()
        page.locator("#home-nav").click(); ready()
        assert page.locator(".case-card").count() == 3
        page.locator("#lab-nav").click(); ready()
        assert page.locator("#lab-play").inner_text() == "Reproducir"
        check("Existing guided catalog retained; navigation stops playback and retains local runs")
        # Read-only utility checks execute the production timestamp selector.
        assert page.evaluate("async()=>{const {sampleIndex}=await import('./transient-lab.js'); return [-1,0,.006,.009,10].map(t=>sampleIndex([0,.005,.01],t));}") == [0,0,1,2,2]
        assert not evidence["console_errors"] and not evidence["page_errors"]
        assert all(req["method"] == "GET" and not req["has_body"] for req in evidence["requests"])
        evidence["runtime"] = json.loads(page.locator("#runtime-identity").text_content())
        check("No console/page errors or outbound result/prediction requests")
        browser.close()
    (args.output / "evidence.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("PASS H30-C browser gate",flush=True)


if __name__ == "__main__":
    main()
