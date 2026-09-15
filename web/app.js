import { mountTransientLab } from "./transient-lab.js";
import { Runtime } from "./runtime.js";
import { trajectoryPlots } from "./plots.js";
import { design, diagram } from "./visuals.js";

const view = document.querySelector("#view");
const errorBox = document.querySelector("#error");
const phases = ["Observar", "Predecir", "Simular", "Intervenir", "Comparar", "Explicar"];
const stateLabels = {
  loading_pyodide: "Preparando el simulador…", loading_wheel: "Cargando SincroLab…",
  ready: "Entorno listo", running: "Ejecutando…", error: "Error",
};
const errorLabels = {
  pyodide_bootstrap: "No se pudo cargar el entorno de cálculo. Comprueba la conexión y recarga la página.",
  wheel_load: "No se pudo cargar o verificar el simulador. Recarga la página; si el fallo persiste, consulta el diagnóstico técnico en la consola.",
  sincrolab_import: "No se pudo iniciar SincroLab. Recarga la página; el diagnóstico técnico está en la consola.",
  invalid_input: "La entrada no es válida para esta operación. Revisa la predicción, los parámetros, sus límites y el orden de los tiempos.",
  portable_error: "El simulador no pudo completar la operación. Consulta la consola para el diagnóstico técnico.",
  unexpected: "Ocurrió un fallo inesperado. Consulta la consola; si el entorno no responde, recarga la página.",
  not_ready: "Espera a que el entorno esté listo y termine la operación actual.",
};
const session = { content: null, sourceCatalog: [], catalog: [], case: null, phase: "Observar", changes: [], prediction: "",
  hints: [], solution: null, result: null, history: [], freeConfig: null, freeResult: null, page: "home" };
let busy = true;
let labView = null;
const labMemory = {};
function leaveLab() { labView?.destroy(); labView = null; }
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
  const active = { home:"start-nav", cases:"home-nav", guided:"home-nav", learn:"learn-nav", free:"free-nav", lab:"lab-nav" }[session.page];
  for (const node of document.querySelectorAll(".sidebar nav button")) {
    if (node.id === active) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  }
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
  session.completed ??= new Set();
  if (session.phase !== phase) session.completed.add(session.phase);
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
      if (typeof value === "number") cell.className = "numeric";
      cell.title = value == null ? "" : String(value);
      row.append(cell);
    }
    body.append(row);
  }
  tableNode.append(head, body);
  wrapper.append(tableNode);
  return wrapper;
}
function meaning(key) { return session.content.meanings.find(item => item.key === key); }
function quantity(key) { return session.content.quantities.find(item => item.key === key); }
function quantityLabel(key) {
  const item = quantity(key);
  return `${item.label} · ${item.symbol}${item.unit ? ` (${item.unit})` : ""}`;
}
function guidance() { return session.content.cases.find(item => item.case_id === session.case.case_id); }
function configRows(value, advanced = false, prefix = "") {
  return Object.entries(value).filter(([key]) => key !== "schema_version").flatMap(([key, item]) => {
    if (item !== null && typeof item === "object") return configRows(item, advanced, `${key}.`);
    const metadata = quantity(key);
    if (advanced) return [[metadata
      ? `${quantityLabel(key)} · ${metadata.description} [${prefix}${key}]`
      : `${prefix}${key}`, item]];
    return metadata && metadata.disclosure === "basic" ? [[`${quantityLabel(key)} · ${metadata.description}`, item]] : [];
  });
}
function configurationPanel(value) {
  const holder = element("section");
  holder.append(table(["Parámetro", "Valor"], configRows(value)),
    details("Detalles avanzados · configuración completa", table(["Identificador técnico", "Valor"], configRows(value, true))));
  return holder;
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
  leaveLab();
  session.page = "home";
  view.replaceChildren(element("p", "LABORATORIO DE ESTABILIDAD TRANSITORIA", "eyebrow"),
    element("h1", "Una misma falla. ¿El mismo desenlace?"),
    element("p", "Observa un generador respecto de la red. Predice qué pasará, cambia cuánto dura una falla y descubre por qué cambia el movimiento.", "home-intro muted"));
  const hero = element("div", undefined, "home-hero");
  hero.append(element("p", "EMPIEZA AQUÍ · RECORRIDO PARA PRINCIPIANTES", "eyebrow"),
    element("h2", "Primero observa. Después explica."),
    element("p", "No necesitas conocer la ecuación de movimiento. Una comparación y una pregunta bastan para comenzar."));
  const links = actions(button("Comenzar el experimento →", openLab, { primary:true, id:"open-transient-lab" }),
    button("Consultar fundamentos →", () => renderLearn()),
    button("Explorar casos guiados →", renderCatalog), button("Modo libre →", openFree));
  links.className = "home-actions";
  const path = element("ol");
  for (const step of session.content.learning_path) path.append(element("li", `${step.label}. ${step.description}`));
  const route = details("Tu recorrido de aprendizaje", path); route.className = "home-path";
  view.append(hero, links, route);
  updateControls();
}
function renderCatalog() {
  leaveLab();
  session.page = "cases";
  view.replaceChildren(element("p", "CASOS GUIADOS", "eyebrow"),
    element("h1", "Tres escenarios para explorar"),
    element("p", "Elige un fenómeno, registra tu predicción y contrástala con una simulación.", "muted"));
  const catalog = element("div", undefined, "catalog");
  for (const [index, item] of session.catalog.entries()) {
    const row = element("article", undefined, "case-card");
    const content = element("div");
    content.append(element("h2", item.title), element("p", item.learning_objective),
      element("span", `${meaning(item.kind).label} · ${meaning(item.difficulty).label}`, "badge"));
    row.append(element("span", String(index + 1).padStart(2, "0"), "case-number"), content,
      button("Abrir →", () => openCase(item.case_id), { id:`case-${item.case_id}` }));
    catalog.append(row);
  }
  view.append(catalog, element("h2", "¿Prefieres tu propio escenario?"), button("Explorar en modo libre →", openFree));
  updateControls();
}
function renderLearn(topicId = session.content.topics[0].topic_id) {
  leaveLab();
  session.page = "learn";
  view.replaceChildren(element("p", "APRENDER", "eyebrow"), element("h1", "Fundamentos y modelo"));
  if (labMemory.a) view.append(button("← Volver a mi experimento", openLab, { id:"theory-return-lab" }));
  if (session.case) {
    const index = session.content.cases.findIndex(item => item.case_id === session.case.case_id);
    const back = button(`← Volver al Caso ${index + 1} · ${session.phase}`, renderCase, { id:"theory-return-case" });
    back.className = "link"; view.append(back);
  }
  const columns = element("div", undefined, "learn-layout");
  const navigation = element("nav", undefined, "topic-nav"); navigation.setAttribute("aria-label", "Temas para aprender");
  const label = element("label", "Tema para aprender", "topic-picker");
  const select = element("select"); select.id = "theory-topics";
  const groups = element("div", undefined, "topic-groups");
  for (const group of design.topic_groups) {
    const options = element("optgroup"); options.label = group.label;
    groups.append(element("h3", group.label));
    for (const [index, topic] of session.content.topics.entries()) {
      if (index < group.start || index >= group.stop) continue;
      const option = element("option", topic.title); option.value = topic.topic_id; options.append(option);
      const control = button(`${String(index + 1).padStart(2, "0")}  ${topic.title}`, () => renderLearn(topic.topic_id), { id:`topic-nav-${topic.topic_id}` });
      if (topic.topic_id === topicId) control.setAttribute("aria-current", "true");
      groups.append(control);
    }
    select.append(options);
  }
  const glossary = element("option", "Glosario"); glossary.value = "glossary"; select.append(glossary);
  select.value = topicId; select.addEventListener("change", () => renderLearn(select.value));
  groups.append(button("Glosario →", () => renderLearn("glossary")));
  label.append(select); navigation.append(label, groups); columns.append(navigation);
  const article = element("article", undefined, "lesson");
  if (topicId === "glossary") {
    article.append(element("h2", "Glosario"));
    for (const term of session.content.glossary) article.append(element("h3", term.label), element("p", term.description));
  } else {
    const topic = session.content.topics.find(item => item.topic_id === topicId);
    article.append(element("h2", topic.title), element("p", "OBJETIVO DE APRENDIZAJE", "eyebrow"),
      element("p", topic.learning_objective, "lesson-objective"));
    for (const [index, block] of topic.blocks.entries()) {
      const section = element("section"); section.dataset.blockKind = block.kind;
      section.append(element("h3", session.content.block_labels.find(item => item.key === block.kind).label), element("p", block.text));
      article.append(section);
      if (index === 0) for (const [key, metadata] of Object.entries(design.diagrams)) {
        if (metadata.topics.includes(topicId)) article.append(diagram(key));
      }
    }
    const links = element("div", undefined, "lesson-links");
    if (topic.prerequisite_topic_ids.length) links.append(element("h3", "Repasar conceptos"));
    for (const key of topic.prerequisite_topic_ids) links.append(
      button(session.content.topics.find(item => item.topic_id === key).title, () => renderLearn(key), { id:`theory-topic-${key}` }));
    for (const key of topic.case_ids) {
      const index = session.content.cases.findIndex(item => item.case_id === key);
      links.append(button(`Caso ${index + 1}: ${session.content.cases[index].concept} →`, () => openCase(key), { id:`theory-case-${key}` }));
    }
    article.append(links);
    const index = session.content.topics.indexOf(topic), next = session.content.topics[index + 1], previous = session.content.topics[index - 1];
    const paging = element("div", undefined, "lesson-next");
    if (previous) paging.append(button("← Tema anterior", () => renderLearn(previous.topic_id), { id:"theory-previous" }));
    if (next) paging.append(button(`Continuar: ${next.title} →`, () => renderLearn(next.topic_id), { primary:true, id:"theory-next" }));
    article.append(paging);
  }
  article.append(button("Ir a casos guiados", renderCatalog));
  columns.append(article); view.append(columns);
  updateControls();
}
async function openCase(caseId) {
  if (session.case?.case_id !== caseId) {
    const item = await runtime.call("guided_show", { case_id: caseId });
    Object.assign(session, { case: item, phase: "Observar", changes: [], prediction: "", hints: [],
      solution: null, result: null, history: [], completed: new Set() });
  }
  renderCase();
}
function renderCase() {
  leaveLab();
  session.page = "guided";
  const item = session.case;
  view.replaceChildren(button("← Casos guiados", renderCatalog), element("p", meaning(item.kind).label, "eyebrow"),
    element("h1", item.title), element("span", meaning(item.difficulty).label, "badge"));
  const nav = element("nav", undefined, "phases"); nav.setAttribute("aria-label", "Fases del caso guiado");
  for (const [index, phase] of phases.entries()) {
    const control = button("", () => go(phase), {
      locked: !session.result && index > 1, id: `phase-${index}`,
    });
    const locked = !session.result && index > 1;
    const state = phase === session.phase ? "current" : locked ? "locked" : session.completed?.has(phase) ? "completed" : "available";
    const labels = { current:"Actual", locked:"Bloqueada", completed:"Completada", available:"Disponible" };
    control.dataset.phaseState = state;
    control.setAttribute("aria-label", `${phase} · ${labels[state]}`);
    control.append(element("span", state === "completed" ? "✓" : state === "locked" ? "·" : String(index + 1), "step-index"), element("span", phase));
    if (phase === session.phase) control.setAttribute("aria-current", "step");
    nav.append(control);
  }
  view.append(nav, element("h2", session.phase));
  ({ Observar: renderObserve, Predecir: renderPredict, Simular: renderResult,
    Intervenir: renderIntervene, Comparar: renderCompare, Explicar: renderExplain })[session.phase]();
  updateControls();
}
function renderPreparation(compact = false) {
  const content = guidance();
  const holder = element("section"); holder.id = "case-preparation"; holder.className = "preparation";
  const expanded = element("div");
  for (const [key, title] of [["remember", "Qué debes recordar"], ["observe", "Qué debes observar"],
    ["experimental_question", "Pregunta experimental"], ["prediction_guidance", "Antes de predecir"]]) {
    (compact && key !== "prediction_guidance" ? expanded : holder).append(element("h3", title), element("p", content[key]));
  }
  if (compact) holder.append(details("Recordar el contexto y la pregunta experimental", expanded));
  const links = element("div", undefined, "review-links");
  for (const key of content.topic_ids) links.append(
    button(session.content.topics.find(topic => topic.topic_id === key).title, () => renderLearn(key), { id:`review-${key}` }));
  for (const control of links.children) control.className = "link";
  (compact ? expanded : holder).append(links); view.append(holder);
}
function renderObserve() {
  const item = session.case;
  view.append(element("h3", "Objetivo de aprendizaje"), element("p", item.learning_objective),
    element("p", item.context));
  view.append(diagram("timeline"));
  renderPreparation();
  view.append(details("Parámetros de la configuración inicial", configurationPanel(item.baseline_config)),
    element("p", item.provenance, "muted"), button("Registrar mi predicción", () => go("Predecir"), { primary:true, id:"begin-prediction" }));
}
function renderPredict() {
  const start = view.children.length;
  renderPreparation(true);
  view.append(element("p", session.case.prediction_prompt));
  const needsChange = session.case.kind === "inertia_effect";
  if (needsChange) {
    const parameter = session.case.editable_parameters[0];
    const value = session.changes.find(item => item.key === parameter.key)?.value ?? parameter.baseline_value;
    const editor = numericField(parameter.key, "Inercia del próximo intento", value, parameter);
    editor.id = "prediction-intervention";
    editor.append(element("small", 'Configuración inicial: ' + parameter.baseline_value + ' s. Elige un valor distinto para comparar dos respuestas.'));
    editor.querySelector("input").addEventListener("input", event => {
      const input = event.target, next = input.valueAsNumber;
      session.changes = input.checkValidity() && next !== parameter.baseline_value ? [{ key:parameter.key, value:next }] : [];
      session.prediction = "";
      document.querySelectorAll("#prediction input").forEach(radio => { radio.checked = false; });
      document.querySelector("#run-guided").dataset.locked = "true";
      updateControls();
    });
    view.append(editor);
  }
  if (!needsChange) {
    if (session.changes.length) view.append(table(["Configuración del próximo intento", "Valor"], session.changes.map(x => [quantityLabel(x.key), x.value])));
    else view.append(element("p", "Se ejecutará la configuración inicial del caso.", "muted"));
  }
  const choices = element("fieldset", undefined, "prediction-choices"); choices.id = "prediction";
  choices.append(element("legend", "Tu predicción, antes de simular"));
  for (const option of session.case.prediction_options) {
    const choice = element("label", undefined, "prediction-choice");
    const radio = element("input"); radio.type = "radio"; radio.name = "prediction"; radio.value = option;
    radio.checked = session.prediction === option;
    const description = element("span");
    description.append(element("strong", meaning(option).label), element("small", meaning(option).description));
    radio.addEventListener("change", () => {
      session.prediction = radio.value;
      document.querySelector("#run-guided").dataset.locked = String(!session.prediction || (needsChange && !session.changes.length));
      updateControls();
    });
    choice.append(radio, description); choices.append(choice);
  }
  view.append(choices);
  if (session.solution) view.append(solutionPanel());
  view.append(button("Simular con esta predicción", runGuided, { primary:true, locked:!session.prediction || (needsChange && !session.changes.length), id:"run-guided" }));
  const columns = element("div", undefined, "prediction-layout");
  const nodes = [...view.children].slice(start), action = element("div", undefined, "prediction-action");
  columns.append(nodes[0]); action.append(...nodes.slice(1)); columns.append(action); view.append(columns);
}
async function runGuided() {
  if (!session.case.prediction_options.includes(session.prediction)) throw { kind:"invalid_input" };
  if (session.case.kind === "inertia_effect" && !session.changes.length) {
    throw { userMessage:"Elige una inercia distinta antes de comparar las respuestas." };
  }
  // Snapshot before execution; the result's prediction is never reconstructed from UI state.
  const request = { schema_version:session.case.schema_version, case_id:session.case.case_id,
    prediction:session.prediction, changes:structuredClone(session.changes),
    hints_revealed:session.hints.length, reveal_solution:session.solution !== null };
  const result = await runtime.call("guided_run", request);
  session.result = result;
  session.completed.add("Predecir");
  session.history.push(result);
  session.prediction = "";
  session.phase = session.history.length === 1 ? "Simular" : "Comparar";
  renderCase();
}
function evaluationPanel(value, curves) {
  const holder = element("section");
  const status = element("p", meaning(value.first_swing.status).label, "result-status");
  status.dataset.status = value.first_swing.status;
  holder.append(status, element("p", meaning(value.first_swing.reason).label, "muted"),
    trajectoryPlots(curves, session.content.quantities), element("h3", "Interpretación"), element("p", value.explanation.summary));
  const legend = element("p", undefined, "legend");
  curves.forEach((curve, i) => legend.append(element("span", `${i === 0 && curves.length > 1 ? "╌" : "—"} ${curve.name}`, i === 0 && curves.length > 1 ? "baseline" : "attempt")));
  holder.append(legend, details("Configuración de esta ejecución", configurationPanel(value.configuration)),
    details("Evidencia avanzada · diagnóstico e intervalos de muestras", element("pre", JSON.stringify(value.first_swing, null, 2))));
  return holder;
}
function curves() {
  return [{ name:"Configuración inicial", trajectory:session.result.baseline_evaluation.trajectory, configuration:session.result.baseline_evaluation.configuration },
    { name:"Intento", trajectory:session.result.attempted_evaluation.trajectory, configuration:session.result.attempted_evaluation.configuration }];
}
function renderResult() {
  if (session.case.kind === "inertia_effect") {
    const comparison = session.result.scientific_comparison;
    const confrontation = element("section"); confrontation.id = "inertia-confrontation";
    confrontation.append(element("h3", "Contrasta tu predicción"),
      element("p", `Tu predicción: ${meaning(session.result.prediction).label}`),
      table(["Evidencia calculada", "Inicial", "Intento"], [
        [quantityLabel("max_delta_rad"), comparison.baseline_max_delta_rad, comparison.attempted_max_delta_rad],
        [quantityLabel("max_abs_omega_dev_pu"), comparison.baseline_max_abs_omega_dev_pu, comparison.attempted_max_abs_omega_dev_pu],
      ]), element("p", session.result.debrief_summary),
      element("p", "¿Qué evidencia respalda o contradice tu predicción? Contrasta ambas métricas."));
    view.append(confrontation);
  }
  view.append(element("p", `Predicción registrada: ${meaning(session.result.prediction).label}`),
    evaluationPanel(session.result.attempted_evaluation, curves()),
    element("h3", "Qué observar"), element("p", guidance().observe),
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
  label.append(element("small", quantity(key).description));
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
    element("p", session.solution.limitation), table(["Parámetro", "Valor", "Unidad"], session.solution.settings.map(x => [quantityLabel(x.key), x.value, x.unit])));
  return panel;
}
function renderIntervene() {
  view.append(element("p", "Modifica los parámetros permitidos y registra una nueva predicción. La comparación conserva la configuración inicial original."));
  view.append(element("p", guidance().intervene));
  const editor = element("div", undefined, "editor");
  const changed = Object.fromEntries(session.changes.map(x => [x.key, x.value]));
  for (const field of session.case.editable_parameters) editor.append(numericField(field.key, quantityLabel(field.key), changed[field.key] ?? field.baseline_value, { minimum:field.minimum, maximum:field.maximum }));
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
  view.append(element("p", `Predicción registrada: ${meaning(result.prediction).label}`), trajectoryPlots(curves(), session.content.quantities), table(["Evidencia", "Inicial", "Intento"], [
    ["Estado", meaning(comparison.baseline_status).label, meaning(comparison.attempted_status).label],
    ["Razón", meaning(comparison.baseline_reason).label, meaning(comparison.attempted_reason).label],
    [quantityLabel("max_delta_rad"), comparison.baseline_max_delta_rad, comparison.attempted_max_delta_rad],
    [quantityLabel("max_abs_omega_dev_pu"), comparison.baseline_max_abs_omega_dev_pu, comparison.attempted_max_abs_omega_dev_pu],
  ]), table(["Parámetro", "Inicial", "Intento", "Unidad"], result.changed_parameters.map(x => [quantityLabel(x.key), x.baseline_value, x.attempted_value, x.unit])),
  element("p", "╌ Configuración inicial · — Intento", "legend"), element("h3", "Intentos de este caso · solo en esta sesión"),
  table(["Intento", "Predicción", "Estado observado", "Cambios"], session.history.map((item, i) => [i + 1, meaning(item.prediction).label,
    meaning(item.attempted_evaluation.first_swing.status).label, item.changed_parameters.map(x => `${quantityLabel(x.key)}: ${x.baseline_value} → ${x.attempted_value} ${x.unit}`).join("; ") || "Sin cambios"])),
  actions(button("Explicar lo observado", () => go("Explicar"), { primary:true }), button("Nueva intervención", () => go("Intervenir"))));
}
function explanation(value) {
  const holder = element("section", undefined, "explanation");
  holder.append(element("h3", value.title), element("p", value.summary));
  const evidence = element("ul", undefined, "evidence");
  for (const item of value.evidence) evidence.append(element("li", `${item.statement} (${item.key}: ${item.value}${item.unit ? ` ${item.unit}` : ""})`));
  holder.append(details("Evidencia avanzada · valores e identificadores", evidence), element("h3", "Hipótesis y limitaciones"));
  for (const text of value.limitations) holder.append(element("p", text));
  return holder;
}
function renderExplain() {
  const result = session.result;
  view.append(element("p", guidance().explain), element("p", result.debrief_summary), element("p", result.goal_evaluation.evidence));
  result.debrief_limitations.forEach(text => view.append(element("p", text, "muted")));
  view.append(explanation(result.attempted_evaluation.explanation));
  if (result.critical_clearing_bracket) view.append(element("h3", "Intervalo de despeje crítico"),
    table(["Magnitud", "Valor"], session.content.quantities.filter(item => item.key in result.critical_clearing_bracket)
      .map(item => [quantityLabel(item.key), result.critical_clearing_bracket[item.key]])),
    details("Detalles avanzados · intervalo de despeje", table(["Identificador técnico", "Valor"], configRows(result.critical_clearing_bracket, true))),
    explanation(result.critical_clearing_explanation));
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
    const source = await runtime.call("guided_show", { case_id:session.sourceCatalog[0].case_id });
    session.freeConfig = source.baseline_config;
  }
  renderFree();
}
function renderFree() {
  leaveLab();
  session.page = "free";
  view.replaceChildren(element("p", "EXPLORACIÓN ABIERTA", "eyebrow"), element("h1", "Modo libre"),
    element("p", "La configuración sintética parte del experimento de despeje. Edita inercia, despeje, horizonte y paso temporal. El estado inicial y los demás parámetros se conservan explícitamente.", "muted"));
  const config = session.freeConfig;
  const editor = element("div", undefined, "editor");
  for (const [key, value] of [["H_s", config.parameters.H_s],
    ["t_clear_s", config.network.t_clear_s], ["t_end_s", config.t_end_s], ["dt_s", config.dt_s]]) {
    editor.append(numericField(key, quantityLabel(key), value));
  }
  view.append(editor, button("Simular", async () => {
    const values = readNumbers(editor);
    const request = structuredClone(session.freeConfig);
    request.parameters.H_s = values.H_s; request.network.t_clear_s = values.t_clear_s;
    request.t_end_s = values.t_end_s; request.dt_s = values.dt_s;
    const result = await runtime.call("evaluate_transient", request);
    session.freeConfig = result.configuration; session.freeResult = result; renderFree();
  }, { primary:true, id:"run-free" }), details("Configuración de partida", configurationPanel(config)));
  if (session.freeResult) {
    const result = session.freeResult;
    view.append(element("h2", "Última ejecución completada"), evaluationPanel(result, [{ name:"Ejecución", trajectory:result.trajectory, configuration:result.configuration }]),
      explanation(result.explanation), button("Descargar resultado JSON", () => download(result, "sincrolab-free-result.json")));
  }
  updateControls();
}

async function openLab() {
  leaveLab();
  session.labDefinition ??= await runtime.call("transient_lab");
  session.page = "lab";
  labMemory.call = (operation, payload) => runtime.call(operation, payload);
  labMemory.openTheory = () => perform(() => renderLearn("swing-equation"));
  labMemory.synchronism = session.content.topics.find(topic => topic.topic_id === "synchronous-generator")
    .blocks.find(block => block.kind === "key-idea").text;
  labView = mountTransientLab(view, session.labDefinition, labMemory, perform);
  updateControls();
}

document.querySelector("#lab-nav").addEventListener("click", () => perform(openLab));
document.querySelector("#start-nav").addEventListener("click", () => perform(renderHome));
document.querySelector("#home-nav").addEventListener("click", () => perform(renderCatalog));
document.querySelector("#learn-nav").addEventListener("click", () => perform(() => renderLearn()));
document.querySelector("#free-nav").addEventListener("click", () => perform(openFree));
document.querySelector(".brand").addEventListener("click", event => { event.preventDefault(); perform(renderHome); });

try {
  const identity = await runtime.ready;
  document.querySelector("#runtime-identity").textContent = JSON.stringify(identity, null, 2);
  session.content = await runtime.call("learning_content");
  session.sourceCatalog = await runtime.call("guided_list");
  session.catalog = session.content.cases.map(item => session.sourceCatalog.find(source => source.case_id === item.case_id));
  busy = false;
  renderHome();
} catch (error) {
  busy = false;
  showError(error);
}
