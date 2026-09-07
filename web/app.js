import { Runtime } from "./runtime.js";
import { trajectoryPlots } from "./plots.js";

const view = document.querySelector("#view");
const errorBox = document.querySelector("#error");
const phases = ["Observar", "Predecir", "Simular", "Intervenir", "Comparar", "Explicar"];
const stateLabels = {
  loading_pyodide: "Cargando Pyodide…", loading_wheel: "Cargando e instalando SincroLab…",
  ready: "Entorno listo", running: "Ejecutando…", error: "Error",
};
const errorLabels = {
  pyodide_bootstrap: "No se pudo cargar Pyodide o NumPy. Comprueba la conexión al CDN y recarga la página.",
  wheel_load: "No se pudo cargar o verificar el wheel. Vuelve a ensamblar el sitio y recarga la página.",
  sincrolab_import: "No se pudo importar SincroLab. Comprueba el wheel y recarga la página.",
  invalid_input: "La entrada no es válida para esta operación. Revisa la predicción, los parámetros, sus límites y el orden de los tiempos.",
  portable_error: "La API portable no pudo completar la operación. Consulta la consola para el diagnóstico técnico.",
  unexpected: "Ocurrió un fallo inesperado. Consulta la consola; si el entorno no responde, recarga la página.",
  not_ready: "Espera a que el entorno esté listo y termine la operación actual.",
};
const session = { catalog: [], case: null, phase: "Observar", changes: [], prediction: "",
  hints: [], solution: null, result: null, history: [], freeConfig: null, freeResult: null, page: "home" };
let busy = true;
const runtime = new Runtime(updateState);

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, action, { primary = false, locked = false, id } = {}) {
  const node = element("button", text, primary ? "primary" : "");
  node.type = "button";
  node.dataset.locked = String(locked);
  if (id) node.id = id;
  node.addEventListener("click", () => perform(action));
  return node;
}
function updateState(value) {
  const status = document.querySelector("#runtime-status");
  status.textContent = stateLabels[value] ?? stateLabels.error;
  status.dataset.state = value;
  updateControls();
}
function updateControls() {
  for (const node of document.querySelectorAll("button, input, select, textarea")) {
    node.disabled = busy || runtime.state !== "ready" || node.dataset.locked === "true";
  }
  view.setAttribute("aria-busy", String(busy));
}
function showError(error) {
  console.error("SincroLab UI", error);
  errorBox.textContent = errorLabels[error?.kind] ?? error?.userMessage ?? errorLabels.unexpected;
  errorBox.hidden = false;
  updateState("error");
}
async function perform(action) {
  if (busy || runtime.state !== "ready") return;
  busy = true;
  errorBox.hidden = true;
  updateControls();
  try { await action(); }
  catch (error) { showError(error); }
  finally { busy = false; updateControls(); }
}
function go(phase) {
  if (!session.result && !phases.slice(0, 2).includes(phase)) {
    throw { userMessage: "Primero registra una predicción y ejecuta el caso." };
  }
  session.phase = phase;
  renderCase();
}
function table(headers, rows) {
  const wrapper = element("div", undefined, "table-wrap");
  const tableNode = element("table");
  const head = element("thead");
  const heading = element("tr");
  for (const title of headers) { const th = element("th", title); th.scope = "col"; heading.append(th); }
  head.append(heading);
  const body = element("tbody");
  for (const values of rows) {
    const row = element("tr");
    for (const value of values) {
      // Display precision is independent of canonical result/JSON precision.
      const display = typeof value === "number" ? String(Number(value.toPrecision(8))) : value == null ? "—" : String(value);
      const cell = element("td", display);
      cell.title = value == null ? "" : String(value);
      row.append(cell);
    }
    body.append(row);
  }
  tableNode.append(head, body);
  wrapper.append(tableNode);
  return wrapper;
}
function configRows(value, prefix = "") {
  return Object.entries(value).filter(([key]) => key !== "schema_version").flatMap(([key, item]) =>
    item !== null && typeof item === "object" ? configRows(item, `${key}.`) : [[`${prefix}${key}`, item]]);
}
function details(title, content) {
  const node = element("details");
  node.append(element("summary", title), content);
  return node;
}
function actions(...nodes) { const node = element("div", undefined, "actions"); node.append(...nodes); return node; }
function download(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = element("a"); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
function renderHome() {
  session.page = "home";
  view.replaceChildren(element("p", "LABORATORIO EDUCATIVO · MODELO CLÁSICO SMIB", "eyebrow"),
    element("h1", "Casos guiados"), element("p", "Elige un fenómeno, registra tu predicción y contrástala con una simulación.", "muted"));
  const catalog = element("div", undefined, "catalog");
  for (const [index, item] of session.catalog.entries()) {
    const card = element("article", undefined, "case-card");
    const content = element("div");
    content.append(element("p", `CASO ${index + 1} · ${item.kind}`, "eyebrow"), element("h2", item.title),
      element("p", item.learning_objective), element("span", item.difficulty, "badge"));
    card.append(content, button("Abrir caso", () => openCase(item.case_id), { id: `case-${item.case_id}` }));
    catalog.append(card);
  }
  view.append(catalog, element("p", "Los textos científicos de los casos conservan el contenido original en inglés. Los controles del laboratorio están en español.", "muted"),
    button("Explorar en modo libre", openFree));
  updateControls();
}
async function openCase(caseId) {
  if (session.case?.case_id !== caseId) {
    const item = await runtime.call("guided_show", { case_id: caseId });
    Object.assign(session, { case: item, phase: "Observar", changes: [], prediction: "", hints: [],
      solution: null, result: null, history: [] });
  }
  renderCase();
}
function renderCase() {
  session.page = "guided";
  const item = session.case;
  view.replaceChildren(button("← Casos guiados", renderHome), element("p", item.kind, "eyebrow"),
    element("h1", item.title), element("span", item.difficulty, "badge"));
  const nav = element("nav", undefined, "phases"); nav.setAttribute("aria-label", "Fases del caso guiado");
  for (const [index, phase] of phases.entries()) {
    const control = button(`${index + 1}. ${phase}`, () => go(phase), {
      locked: !session.result && index > 1, id: `phase-${index}`,
    });
    if (phase === session.phase) control.setAttribute("aria-current", "step");
    nav.append(control);
  }
  view.append(nav, element("h2", session.phase));
  ({ Observar: renderObserve, Predecir: renderPredict, Simular: renderResult,
    Intervenir: renderIntervene, Comparar: renderCompare, Explicar: renderExplain })[session.phase]();
  updateControls();
}
function renderObserve() {
  const item = session.case;
  view.append(element("h3", "Objetivo de aprendizaje"), element("p", item.learning_objective),
    element("p", item.context), details("Configuración inicial · unidades en cada campo", table(["Parámetro", "Valor"], configRows(item.baseline_config))),
    element("p", item.provenance, "muted"), button("Registrar mi predicción", () => go("Predecir"), { primary:true, id:"begin-prediction" }));
}
function renderPredict() {
  view.append(element("p", session.case.prediction_prompt));
  if (session.changes.length) view.append(table(["Configuración del próximo intento", "Valor"], session.changes.map(x => [x.key, x.value])));
  else view.append(element("p", "Se ejecutará la configuración inicial del caso.", "muted"));
  const label = element("label", undefined, "field editor");
  label.append(element("span", "Tu predicción, antes de simular"));
  const select = element("select"); select.id = "prediction";
  const blank = element("option", "Selecciona una predicción"); blank.value = ""; select.append(blank);
  for (const option of session.case.prediction_options) {
    const node = element("option", option); node.value = option; select.append(node);
  }
  select.value = session.prediction;
  select.addEventListener("change", () => {
    session.prediction = select.value;
    document.querySelector("#run-guided").dataset.locked = String(!session.prediction);
    updateControls();
  });
  label.append(select); view.append(label);
  if (session.solution) view.append(solutionPanel());
  view.append(button("Simular con esta predicción", runGuided, { primary:true, locked:!session.prediction, id:"run-guided" }));
}
async function runGuided() {
  if (!session.case.prediction_options.includes(session.prediction)) throw { kind:"invalid_input" };
  // Snapshot before execution; the result's prediction is never reconstructed from UI state.
  const request = { schema_version:session.case.schema_version, case_id:session.case.case_id,
    prediction:session.prediction, changes:structuredClone(session.changes),
    hints_revealed:session.hints.length, reveal_solution:session.solution !== null };
  const result = await runtime.call("guided_run", request);
  session.result = result;
  session.history.push(result);
  session.prediction = "";
  session.phase = session.history.length === 1 ? "Simular" : "Comparar";
  renderCase();
}
function evaluationPanel(value, curves) {
  const holder = element("section");
  const status = element("p", value.first_swing.status.toUpperCase(), "result-status");
  status.dataset.status = value.first_swing.status;
  holder.append(status, element("p", value.first_swing.reason, "muted"), trajectoryPlots(curves));
  const legend = element("p", undefined, "legend");
  curves.forEach((curve, i) => legend.append(element("span", `${i === 0 && curves.length > 1 ? "╌" : "—"} ${curve.name}`, i === 0 && curves.length > 1 ? "baseline" : "attempt")));
  holder.append(legend, details("Configuración de esta ejecución", table(["Parámetro", "Valor"], configRows(value.configuration))),
    details("Diagnóstico y brackets de muestras", element("pre", JSON.stringify(value.first_swing, null, 2))));
  return holder;
}
function curves() {
  return [{ name:"Baseline original", trajectory:session.result.baseline_evaluation.trajectory },
    { name:"Intento", trajectory:session.result.attempted_evaluation.trajectory }];
}
function renderResult() {
  view.append(element("p", `Predicción registrada: ${session.result.prediction}`),
    evaluationPanel(session.result.attempted_evaluation, curves()),
    actions(button("Intervenir en el caso", () => go("Intervenir"), { primary:true }), button("Ver explicación", () => go("Explicar"))));
}
function numericField(key, labelText, value, { minimum, maximum, unit = "" } = {}) {
  const label = element("label", undefined, "field");
  label.append(element("span", `${labelText}${unit ? ` · ${unit}` : ""}`));
  const input = element("input"); input.type = "number"; input.step = "any";
  input.id = `input-${key}`; input.name = key; input.value = String(value); input.required = true;
  if (minimum !== undefined) input.min = minimum;
  if (maximum !== undefined) input.max = maximum;
  label.append(input);
  if (minimum !== undefined) label.append(element("small", `Intervalo permitido: ${minimum} a ${maximum} ${unit}`));
  return label;
}
function readNumbers(editor) {
  const entries = [];
  for (const input of editor.querySelectorAll("input")) {
    if (!input.checkValidity() || !Number.isFinite(input.valueAsNumber)) {
      input.reportValidity(); throw { kind:"invalid_input" };
    }
    entries.push([input.name, input.valueAsNumber]);
  }
  return Object.fromEntries(entries);
}
function applyChanges(values) {
  session.changes = Object.entries(values).map(([key, value]) => ({ key, value }));
  session.prediction = "";
  go("Predecir");
}
function solutionPanel() {
  const panel = element("div", undefined, "panel");
  panel.append(element("h3", "Una solución pedagógica posible"), element("p", session.solution.explanation),
    element("p", session.solution.limitation), table(["Parámetro", "Valor", "Unidad"], session.solution.settings.map(x => [x.key, x.value, x.unit])));
  return panel;
}
function renderIntervene() {
  view.append(element("p", "Modifica los parámetros permitidos y registra una nueva predicción. La comparación conserva el baseline original."));
  const editor = element("div", undefined, "editor");
  const changed = Object.fromEntries(session.changes.map(x => [x.key, x.value]));
  for (const field of session.case.editable_parameters) editor.append(numericField(field.key, field.label, changed[field.key] ?? field.baseline_value, field));
  const hints = element("div"); hints.id = "hints";
  const fillHints = () => hints.replaceChildren(...session.hints.map((text, i) => element("p", `Pista ${i + 1}: ${text}`)));
  fillHints();
  const hintButton = button(`Pista ${session.hints.length + 1}`, async () => {
    const result = await runtime.call("guided_hints", { case_id:session.case.case_id, count:session.hints.length + 1 });
    session.hints = result.hints; fillHints();
    hintButton.textContent = session.hints.length < session.case.hints_available ? `Pista ${session.hints.length + 1}` : "Pistas consultadas";
    hintButton.dataset.locked = String(session.hints.length >= session.case.hints_available);
  }, { locked:session.hints.length >= session.case.hints_available, id:"next-hint" });
  const reveal = button("Mostrar una solución", async () => {
    session.solution = await runtime.call("guided_solution", { case_id:session.case.case_id });
    applyChanges(Object.fromEntries(session.solution.settings.map(x => [x.key, x.value])));
  }, { locked:!session.case.has_pedagogical_solution, id:"reveal-solution" });
  view.append(editor, button("Predecir este nuevo intento", () => applyChanges(readNumbers(editor)), { primary:true, id:"apply-changes" }), actions(hintButton, reveal), hints);
  if (session.solution) view.append(solutionPanel());
}
function renderCompare() {
  const result = session.result;
  const comparison = result.scientific_comparison;
  view.append(element("p", `Predicción registrada: ${result.prediction}`), table(["Evidencia", "Inicial", "Intento"], [
    ["Estado", comparison.baseline_status, comparison.attempted_status],
    ["Razón", comparison.baseline_reason, comparison.attempted_reason],
    ["Máximo delta_rad", comparison.baseline_max_delta_rad, comparison.attempted_max_delta_rad],
    ["Máximo |omega_dev_pu|", comparison.baseline_max_abs_omega_dev_pu, comparison.attempted_max_abs_omega_dev_pu],
  ]), table(["Parámetro", "Inicial", "Intento", "Unidad"], result.changed_parameters.map(x => [x.key, x.baseline_value, x.attempted_value, x.unit])),
  trajectoryPlots(curves()), element("p", "╌ Baseline original · — Intento", "legend"), element("h3", "Intentos de este caso · solo en esta sesión"),
  table(["Intento", "Predicción", "Estado observado", "Cambios"], session.history.map((item, i) => [i + 1, item.prediction,
    item.attempted_evaluation.first_swing.status, item.changed_parameters.map(x => `${x.key}: ${x.baseline_value} → ${x.attempted_value} ${x.unit}`).join("; ") || "Sin cambios"])),
  actions(button("Explicar lo observado", () => go("Explicar"), { primary:true }), button("Nueva intervención", () => go("Intervenir"))));
}
function explanation(value) {
  const holder = element("section", undefined, "explanation");
  holder.append(element("h3", value.title), element("p", value.summary));
  const evidence = element("ul", undefined, "evidence");
  for (const item of value.evidence) evidence.append(element("li", `${item.statement} (${item.key}: ${item.value}${item.unit ? ` ${item.unit}` : ""})`));
  holder.append(evidence, element("h3", "Hipótesis y limitaciones"));
  for (const text of value.limitations) holder.append(element("p", text));
  return holder;
}
function renderExplain() {
  const result = session.result;
  view.append(element("p", result.debrief_summary), element("p", result.goal_evaluation.evidence));
  result.debrief_limitations.forEach(text => view.append(element("p", text, "muted")));
  view.append(explanation(result.attempted_evaluation.explanation));
  if (result.critical_clearing_bracket) view.append(element("h3", "Intervalo de despeje crítico"),
    table(["Campo del contrato", "Valor"], configRows(result.critical_clearing_bracket)), explanation(result.critical_clearing_explanation));
  view.append(element("h3", "Pregunta conceptual de cierre"));
  for (const question of session.case.conceptual_questions) {
    const panel = element("div", undefined, "panel"); panel.append(element("p", question.prompt));
    const list = element("ul"); question.options.forEach(option => list.append(element("li", `${option.option_id}. ${option.text}`)));
    panel.append(list); view.append(panel);
  }
  view.append(element("p", "Reflexiona sobre las opciones y explica qué evidencia apoya tu respuesta. Esta web no realiza autoevaluación pre/post ni asigna una puntuación.", "muted"),
    actions(button("Descargar resultado JSON", () => download(result, "sincrolab-guided-result.json")), button("Explorar otra intervención", () => go("Intervenir"), { primary:true })));
}
async function openFree() {
  if (!session.freeConfig) {
    const source = await runtime.call("guided_show", { case_id:session.catalog[0].case_id });
    session.freeConfig = source.baseline_config;
  }
  renderFree();
}
function renderFree() {
  session.page = "free";
  view.replaceChildren(element("p", "EXPLORACIÓN ABIERTA", "eyebrow"), element("h1", "Modo libre"),
    element("p", "La configuración parte del primer caso público. Edita inercia, despeje, horizonte y paso temporal. El estado inicial y los demás parámetros se conservan explícitamente.", "muted"));
  const config = session.freeConfig;
  const editor = element("div", undefined, "editor");
  for (const [key, label, value] of [["H_s", "H_s · inercia", config.parameters.H_s],
    ["t_clear_s", "t_clear_s · despeje", config.network.t_clear_s], ["t_end_s", "t_end_s · horizonte", config.t_end_s], ["dt_s", "dt_s · paso temporal", config.dt_s]]) {
    editor.append(numericField(key, label, value, { unit:"s" }));
  }
  view.append(editor, button("Simular", async () => {
    const values = readNumbers(editor);
    const request = structuredClone(session.freeConfig);
    request.parameters.H_s = values.H_s; request.network.t_clear_s = values.t_clear_s;
    request.t_end_s = values.t_end_s; request.dt_s = values.dt_s;
    const result = await runtime.call("evaluate_transient", request);
    session.freeConfig = result.configuration; session.freeResult = result; renderFree();
  }, { primary:true, id:"run-free" }), details("Configuración completa de partida", table(["Parámetro", "Valor"], configRows(config))));
  if (session.freeResult) {
    const result = session.freeResult;
    view.append(element("h2", "Última ejecución completada"), evaluationPanel(result, [{ name:"Ejecución", trajectory:result.trajectory }]),
      explanation(result.explanation), button("Descargar resultado JSON", () => download(result, "sincrolab-free-result.json")));
  }
  updateControls();
}

document.querySelector("#home-nav").addEventListener("click", () => perform(renderHome));
document.querySelector("#free-nav").addEventListener("click", () => perform(openFree));
document.querySelector(".brand").addEventListener("click", event => { event.preventDefault(); perform(renderHome); });

try {
  const identity = await runtime.ready;
  document.querySelector("#runtime-identity").textContent = JSON.stringify(identity, null, 2);
  session.catalog = await runtime.call("guided_list");
  busy = false;
  renderHome();
} catch (error) {
  busy = false;
  showError(error);
}
