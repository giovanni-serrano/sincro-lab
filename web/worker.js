import { PYODIDE_BASE, PYODIDE_VERSION } from "./pyodide-config.js";

let bridge;
let busy = false;
const state = (value) => postMessage({ type: "state", state: value });

async function bootstrap() {
  let kind = "pyodide_bootstrap";
  try {
    state("loading_pyodide");
    const { loadPyodide } = await import(`${PYODIDE_BASE}pyodide.mjs`);
    const python = await loadPyodide({ indexURL: PYODIDE_BASE });
    await python.loadPackage(["numpy", "micropip"]);
    kind = "wheel_load";
    state("loading_wheel");
    const manifestResponse = await fetch("./manifest.json", { cache: "no-store" });
    if (!manifestResponse.ok) throw new Error("Missing assembled manifest");
    const manifest = await manifestResponse.json();
    if (!/^sincrolab-[\w.]+-py3-none-any\.whl$/.test(manifest.wheel)) {
      throw new Error("Invalid wheel filename");
    }
    const response = await fetch(`./${manifest.wheel}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Wheel download failed");
    const bytes = await response.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const sha256 = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, "0")).join("");
    if (sha256 !== manifest.wheel_sha256) throw new Error("Wheel SHA-256 mismatch");
    // Install the exact verified bytes; no second download or dependency resolver.
    python.FS.writeFile(`/tmp/${manifest.wheel}`, new Uint8Array(bytes));
    python.globals.set("wheel_uri", `emfs:/tmp/${manifest.wheel}`);
    await python.runPythonAsync("import micropip\nawait micropip.install(wheel_uri, deps=False)");
    kind = "sincrolab_import";
    await python.runPythonAsync("from sincrolab.interfaces.web.bridge import dispatch_json");
    bridge = python.globals.get("dispatch_json");
    const capabilities = JSON.parse(bridge("capabilities", "{}")).data;
    if (capabilities.package_version !== manifest.package_version) {
      throw new Error("Installed package version mismatch");
    }
    const environment = JSON.parse(python.runPython(
      'import json, sys, numpy, sincrolab\njson.dumps({"python": sys.version.split()[0], "numpy": numpy.__version__, "sincrolab": sincrolab.__version__})'
    ));
    postMessage({ type: "ready", identity: {
      ...manifest, pyodide: PYODIDE_VERSION, capabilities, environment,
    } });
    state("ready");
  } catch (error) {
    console.error(kind, error);
    postMessage({ type: "fatal", error: { kind } });
    state("error");
  }
}

self.onmessage = ({ data }) => {
  if (!bridge || busy) {
    postMessage({ type: "result", id: data.id, ok: false, error: { kind: "not_ready" } });
    return;
  }
  busy = true;
  state("running");
  try {
    const response = JSON.parse(bridge(data.operation, JSON.stringify(data.payload ?? {})));
    if (!response.ok) console.error("SincroLab bridge", response.error);
    postMessage({ type: "result", id: data.id, ...response });
  } catch (error) {
    console.error("SincroLab worker", error);
    postMessage({ type: "result", id: data.id, ok: false, error: { kind: "unexpected" } });
  } finally {
    busy = false;
    state("ready");
  }
};

bootstrap();
