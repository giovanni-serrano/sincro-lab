// Presentation only: positions, powers, states and diagnosis arrive from Python.
const NS = "http://www.w3.org/2000/svg";
const seconds = value => `${value.toFixed(3)} s`;
const names = { prefault:"Prefalla", fault:"Falla", postfault:"Posfalla" };
const outcomes = { stable:"Mantiene sincronismo", unstable:"Pierde sincronismo", indeterminate:"Resultado indeterminado" };
const predictions = { maintain:"Mantendrá sincronismo", lose:"Perderá sincronismo", unsure:"No estoy seguro" };
function node(tag, text, cls) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  if (cls) result.className = cls;
  return result;
}
function svg(tag, attrs = {}) {
  const result = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) result.setAttribute(key, value);
  return result;
}
function lock(control, locked) {
  control.dataset.locked = String(locked);
  control.disabled = locked;
}

// Nearest supplied timestamp; no interpolation or extrapolation of the state.
export function sampleIndex(times, requested) {
  let low = 0, high = times.length - 1;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (times[middle] < requested) low = middle + 1;
    else high = middle;
  }
  return low > 0 && requested - times[low - 1] < times[low] - requested ? low - 1 : low;
}

export function mountTransientLab(host, lab, memory, execute) {
  const state = memory;
  state.choice ??= 0;
  state.index ??= 0;
  state.reveal ??= 0;
  state.prediction ??= "";
  state.lessons ??= {};
  state.usedChoices ??= [];
  state.plotMode ??= "first";
  let frame = 0, playing = false, disposed = false;
  const root = node("section", undefined, "transient-lab");
  root.id = "transient-lab";
  root.append(node("p", "EXPERIMENTO · UNA MISMA FALLA", "eyebrow"),
    node("h1", "¿Volverá después de la falla?"));
  const prompt = node("p", undefined, "lab-prompt");
  root.append(prompt);
  const work = node("div", undefined, "lab-work");
  const phenomenon = node("div", undefined, "lab-phenomenon");
  const heading = node("div", undefined, "lab-view-heading");
  const viewTitle = node("h2", "El generador respecto de la red");
  const clock = node("output", "0.000 s", "lab-clock"); clock.id = "lab-time";
  heading.append(viewTitle, clock);
  const angular = svg("svg", { viewBox:"70 32 335 200", role:"img", "aria-label":"Adelanto angular del rotor en una vista que sigue el ciclo eléctrico de la red", class:"lab-angular" });
  const orbit = svg("circle", { cx:190, cy:132, r:92, fill:"none", stroke:"var(--border)", "stroke-width":1 });
  const reference = svg("path", { d:"M190 132H300", stroke:"var(--muted)", "stroke-width":1.5, "stroke-dasharray":"3 4" });
  const referenceText = svg("text", { x:302, y:128, fill:"var(--muted)", "font-size":14 }); referenceText.textContent = "Referencia";
  const referenceText2 = svg("text", { x:302, y:146, fill:"var(--muted)", "font-size":14 }); referenceText2.textContent = "de la red";
  angular.append(orbit, reference, referenceText, referenceText2, svg("circle", {cx:190,cy:132,r:3,fill:"var(--muted)"}));
  const trails = svg("g", {"aria-hidden":"true"});
  const markers = svg("g"); angular.append(trails, markers);
  const readouts = node("div", undefined, "lab-readouts"); readouts.id = "lab-readouts";
  const systems = node("div", undefined, "lab-systems"); systems.id = "lab-systems";
  const referenceCaption = node("p", "Línea punteada: referencia de la red", "lab-reference");
  const observation = node("div", undefined, "lab-observation-cues"); observation.id = "lab-observation-cues";
  phenomenon.append(heading, angular, referenceCaption, readouts, systems, observation);
  const causePanel = node("aside", undefined, "lab-cause"); causePanel.hidden = true; causePanel.tabIndex = 0; causePanel.setAttribute("aria-label", "Causa y nombres formales");
  causePanel.append(node("h2", "¿Qué impulsa el movimiento?"));
  const balances = node("div"); balances.id = "lab-balances";
  const formal = node("p", undefined, "lab-formal"); formal.hidden = true;
  causePanel.append(balances, formal);
  work.append(phenomenon); root.append(work);

  const events = node("section", undefined, "lab-events");
  events.append(node("h2", "Duración de la falla"));
  const timing = node("div", undefined, "lab-timing");
  const duration = node("output"); duration.id = "lab-duration";
  const eventTimes = node("span", undefined, "muted"); eventTimes.id = "lab-event-times";
  timing.append(duration, eventTimes); events.append(timing);
  const eventHelp = node("details", undefined, "lab-definition");
  eventHelp.append(node("summary", "Antes, durante y después de eliminar la falla"), node("p", state.eventHelp));
  events.append(eventHelp);
  const eventWindowEnd = lab.clearing_choices.at(-1).t_clear_s + lab.baseline_config.network.t_fault_s;
  const percent = t => 100 * t / eventWindowEnd;
  const faultTime = lab.baseline_config.network.t_fault_s;
  const tracks = node("div", undefined, "lab-tracks");
  const rows = node("div");
  const editLayer = node("div", undefined, "lab-edit-layer");
  const handle = node("button", "↔", "lab-clear-handle"); handle.id = "lab-clearing-handle";
  handle.type = "button"; handle.setAttribute("role", "slider");
  handle.setAttribute("aria-label", "Límite de despeje: duración de la falla");
  handle.setAttribute("aria-valuemin", lab.clearing_choices[0].fault_duration_s);
  handle.setAttribute("aria-valuemax", lab.clearing_choices.at(-1).fault_duration_s);
  const timeCursor = node("div", undefined, "lab-event-cursor"); timeCursor.setAttribute("aria-hidden", "true");
  editLayer.append(handle); tracks.append(rows, editLayer, timeCursor); events.append(tracks);
  const eventAxis = node("div", undefined, "lab-event-axis");
  eventAxis.append(node("span", "0 s"), node("span", `Ventana de eventos · ${seconds(eventWindowEnd)}`));
  const editNote = node("p", undefined, "lab-edit-note"); events.append(eventAxis, editNote);
  root.append(events);

  const transport = node("div", undefined, "lab-transport");
  function button(id, text, action) {
    const result = node("button", text); result.id = id; result.type = "button";
    result.addEventListener("click", action); return result;
  }
  const play = button("lab-play", "Reproducir", () => playing ? pause() : start());
  const reset = button("lab-reset", "Reiniciar", () => { pause(); state.index = 0; paint(); });
  const scrubLabel = node("label", "Instante físico", "lab-scrub-label");
  const scrub = node("input"); scrub.id = "lab-scrub"; scrub.type = "range"; scrub.min = 0; scrub.step = 1;
  scrub.addEventListener("input", () => { pause(); state.index = Number(scrub.value); paint(); });
  scrubLabel.append(scrub);
  transport.append(play, reset, scrubLabel, node("span", "Cámara lenta · 0.35×", "muted"));
  phenomenon.append(transport);
  const prediction = node("fieldset", undefined, "lab-prediction"); prediction.id = "lab-prediction";
  prediction.append(node("legend", "Antes de simular, ¿qué crees que ocurrirá?"));
  const synchronism = node("details", undefined, "lab-definition");
  synchronism.append(node("summary", "¿Qué significa mantenerse sincronizado?"), node("p", state.synchronism));
  prediction.append(synchronism);
  for (const value of lab.prediction_options) {
    const label = node("label"); const input = node("input");
    input.type = "radio"; input.name = "lab-prediction"; input.value = value; input.checked = state.prediction === value;
    input.addEventListener("change", () => { state.prediction = value; refreshControls(); });
    label.append(input, node("span", predictions[value])); prediction.append(label);
  }
  const run = button("lab-run", "Simular primera corrida", async () => {
    pause();
    await execute(async () => {
      const result = await state.call("phenomenon_run", { clearing_choice_index:state.choice, prediction:state.prediction });
      const label = state.transferPending ? "C" : state.a ? "B" : "A";
      if (label === "B") { delete state.c; delete state.lessons.C; }
      state[label.toLowerCase()] = result.run;
      state.lessons[label] = result.lesson;
      state.usedChoices.push(state.choice);
      state.observedA = Boolean(state.a); state.observedB = Boolean(state.b);
      state.transferDone = label === "C";
      state.transferPending = false;
      state.compare = label !== "A"; state.compared = state.compare;
      state.index = 0; state.prediction = ""; state.plotMode = "first";
      prediction.querySelectorAll("input").forEach(input => { input.checked = false; });
      paint(); start();
      resultBox.scrollIntoView({ block:"nearest" });
    });
  }); run.className = "primary";
  const experimentActions = node("div", undefined, "lab-experiment-actions"); experimentActions.append(prediction, run);
  root.append(experimentActions);
  const resultBox = node("div", undefined, "lab-result"); resultBox.id = "lab-result"; resultBox.setAttribute("aria-live", "polite");
  const revealActions = node("div", undefined, "lab-reveal-actions");
  const compare = button("lab-compare", "Comparar corridas", () => {
    pause(); state.compare = !state.compare; state.index = 0; paint();
  });
  const inspect = button("lab-inspect", "Inspeccionar el primer despeje", () => {
    pause(); state.index = sampleIndex(state.a.playhead_time_s, state.a.evaluation.configuration.network.t_clear_s); paint();
  });
  const longer = button("lab-longer", "Cambiar la duración y predecir otra vez", () => {
    state.compare = false; setChoice(lab.clearing_choices.length - 1);
    prediction.scrollIntoView({ block:"center" });
  });
  const revealCause = button("lab-reveal-cause", "¿Por qué ocurre? Seguir la explicación", () => {
    pause(); state.reveal = 1;
    state.index = state.lessons.A.clearing_index; paint();
    lessonPanel.scrollIntoView({ block:"start" });
  });
  revealActions.append(longer, compare, inspect, revealCause);
  root.append(resultBox, revealActions);
  const reflection = node("label", undefined, "lab-reflection"); reflection.id = "lab-reflection";
  const reflectionPrompt = node("span");
  const reflectionInput = node("textarea"); reflectionInput.id = "lab-reflection-input";
  reflectionInput.rows = 3; reflectionInput.value = state.reflection ?? "";
  reflectionInput.addEventListener("input", () => { state.reflection = reflectionInput.value; });
  reflection.append(reflectionPrompt, reflectionInput, node("small", "Opcional. Solo permanece en esta sesión; no se envía ni se califica."));
  root.append(reflection);
  const graph = node("figure", undefined, "lab-graph"); graph.id = "lab-graph"; graph.hidden = true;
  const graphTitle = node("figcaption", "Evidencia · separación angular en el tiempo");
  const plot = svg("svg", { viewBox:"0 0 800 260", role:"img", "aria-label":"Separación angular continua, en grados, sobre una escala común" });
  const plotActions = node("div", undefined, "lab-plot-actions");
  const firstView = button("lab-first-view", "Primera oscilación", () => { pause(); state.plotMode = "first"; paint(); });
  const fullView = button("lab-full-view", "Trayectoria completa", () => { pause(); state.plotMode = "full"; paint(); });
  plotActions.append(firstView, fullView);
  const plotNote = node("p", undefined, "lab-plot-note"); plotNote.id = "lab-plot-note";
  const cursorNote = node("p", undefined, "lab-cursor-note"); cursorNote.id = "lab-cursor-note";
  graph.append(graphTitle, plotActions, plot, plotNote, cursorNote); root.append(graph);
  const lessonPanel = node("section", undefined, "lab-lesson"); lessonPanel.id = "lab-lesson";
  const stageTitle = node("h2"), stageText = node("p"), stageQuestion = node("p", undefined, "lab-stage-question");
  const nextStage = button("lab-next-explanation", "Continuar", () => {
    pause(); state.reveal += 1; paint(); lessonPanel.scrollIntoView({ block:"start" });
  });
  const previousStage = button("lab-previous-explanation", "← Paso anterior", () => { state.reveal -= 1; paint(); });
  const theory = button("lab-theory", "Profundizar en la ecuación", () => state.openTheory());
  const transfer = button("lab-transfer", "Probar una situación nueva →", async () => {
    pause();
    await execute(async () => {
      const draft = await state.call("phenomenon_transfer", { used_choice_indices:state.usedChoices });
      if (draft.choice_index === null) return;
      state.transferPrompt = draft.prompt; state.transferPending = true; state.transferDone = false;
      state.choice = draft.choice_index; state.prediction = ""; state.compare = false; state.index = 0;
      prediction.querySelectorAll("input").forEach(input => { input.checked = false; });
      paint(); experiment.scrollIntoView({ block:"start" });
    });
  });
  const stageActions = node("div", undefined, "lab-reveal-actions");
  stageActions.append(previousStage, nextStage, theory, transfer);
  lessonPanel.append(stageTitle, stageText, stageQuestion, causePanel, stageActions);
  root.append(lessonPanel);
  const closing = node("p", "Si ambas corridas empiezan igual, ¿por qué despejar la falla no hace que el generador vuelva inmediatamente a su posición inicial?", "lab-closing"); closing.hidden = true;
  const scope = node("p", lab.limitation, "lab-scope"); scope.hidden = true;
  root.append(closing, scope);
  const experiment = node("div", undefined, "lab-experiment");
  const decisions = node("div", undefined, "lab-decisions");
  decisions.append(events, experimentActions, resultBox);
  experiment.append(work, decisions); root.insertBefore(experiment, revealActions);
  host.replaceChildren(root);

  function currentLabel() { return state.c ? "C" : state.b ? "B" : "A"; }
  function runs() {
    if (state.transferPending) return [["C", null]];
    return state.compare ? [["A", state.a], [currentLabel(), current()]] : [[currentLabel(), current()]];
  }
  function current() { return state.transferPending ? null : state.c ?? state.b ?? state.a; }
  function pause() { playing = false; cancelAnimationFrame(frame); play.textContent = "Reproducir"; }
  function start() {
    if (!current() || disposed) return;
    pause();
    const times = current().playhead_time_s;
    const finish = state.plotMode === "first" ?
      Math.max(...runs().map(([label]) => state.lessons[label].first_swing_end_index)) : times.length - 1;
    if (state.index >= finish) state.index = 0;
    playing = true; play.textContent = "Pausar";
    const startWall = performance.now(), startTime = times[state.index];
    function tick(now) {
      if (!playing || disposed) return;
      state.index = Math.min(finish, sampleIndex(times, startTime + (now - startWall) / 1000 * 0.35));
      paint();
      if (state.index === finish) pause();
      else frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
  }
  function setChoice(index) {
    if (!state.observedA || state.compare || handle.disabled) return;
    const next = Math.max(0, Math.min(lab.clearing_choices.length - 1, index));
    if (state.choice === next) return;
    state.transferDone = false;
    pause(); state.choice = next; state.prediction = "";
    prediction.querySelectorAll("input").forEach(input => { input.checked = false; });
    paint();
  }
  handle.addEventListener("keydown", event => {
    const moves = { ArrowRight:1, ArrowUp:1, ArrowLeft:-1, ArrowDown:-1, PageUp:5, PageDown:-5 };
    if (event.key in moves || event.key === "Home" || event.key === "End") {
      event.preventDefault();
      setChoice(event.key === "Home" ? 0 : event.key === "End" ? lab.clearing_choices.length - 1 : state.choice + moves[event.key]);
    }
  });
  let dragging = false;
  function drag(event) {
    const rect = editLayer.getBoundingClientRect();
    const requested = (event.clientX - rect.left) / rect.width * eventWindowEnd;
    setChoice(sampleIndex(lab.clearing_choices.map(choice => choice.t_clear_s), requested));
  }
  handle.addEventListener("pointerdown", event => {
    if (handle.disabled) return;
    pause(); dragging = true; handle.setPointerCapture(event.pointerId); event.preventDefault(); drag(event);
  });
  handle.addEventListener("pointermove", event => { if (dragging) drag(event); });
  handle.addEventListener("pointerup", event => { dragging = false; if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId); });
  handle.addEventListener("pointercancel", () => { dragging = false; });

  function refreshControls() {
    const hasRun = Boolean(current());
    transport.hidden = !hasRun;
    readouts.hidden = !hasRun;
    lock(play, !hasRun); lock(reset, !hasRun); lock(scrub, !hasRun);
    lock(handle, !state.observedA || Boolean(state.compare) || Boolean(state.transferPending));
    lock(run, !lab.prediction_options.includes(state.prediction) || Boolean(state.compare) ||
      Boolean(state.a && !state.transferPending && state.choice === state.a.clearing_choice_index));
    lock(compare, !state.observedA || !state.observedB || Boolean(state.transferPending));
    inspect.hidden = !state.compare;
    compare.hidden = !state.b || Boolean(state.transferPending);
    compare.textContent = state.compare ? "Volver a experimentar" : "Comparar corridas";
    longer.hidden = !state.a || Boolean(state.b) || Boolean(state.transferPending);
    revealCause.hidden = !state.compared || state.reveal >= 1 || Boolean(state.transferPending);
    run.textContent = state.transferPending ? "Confirmar predicción y probar" : state.a ? "Simular nueva duración" : "Confirmar predicción y simular";
    prediction.hidden = Boolean(state.compare);
    run.hidden = prediction.hidden;
    previousStage.hidden = state.reveal <= 1;
    nextStage.hidden = state.reveal >= 6;
    theory.hidden = state.reveal !== 6;
    transfer.hidden = state.reveal !== 6 || Boolean(state.transferDone);
    firstView.setAttribute("aria-pressed", String(state.plotMode === "first"));
    fullView.setAttribute("aria-pressed", String(state.plotMode === "full"));
  }

  function track(label, clear, kind) {
    const row = node("div", undefined, `lab-event-row ${kind}`);
    row.dataset.clearS = clear;
    for (const [text, left, right, phase] of [["Prefalla",0,faultTime,"prefault"], ["Falla",faultTime,clear,"fault"], ["Posfalla",clear,eventWindowEnd,"postfault"]]) {
      const segment = node("span", text, `lab-region ${phase}`);
      segment.style.left = `${percent(left)}%`; segment.style.width = `${percent(right-left)}%`; row.append(segment);
    }
    const tag = node("b", label, "lab-track-label"); row.append(tag); return row;
  }
  function system(label, networkState) {
    const row = node("div", undefined, `lab-system run-${label.toLowerCase()}`); row.dataset.networkState = networkState;
    row.append(node("b", label));
    const drawing = svg("svg", {viewBox:"0 0 340 46", "aria-hidden":"true"});
    drawing.append(svg("circle", {cx:24,cy:23,r:15,fill:"none",stroke:"currentColor","stroke-width":1.5}),
      svg("path", {d:"M39 23H293M293 5V41",fill:"none",stroke:"currentColor","stroke-width":2}));
    const generator = svg("text", {x:18,y:28,"font-size":14,fill:"currentColor"}); generator.textContent="G";
    const grid = svg("text", {x:305,y:30,"font-size":23,fill:"currentColor"}); grid.textContent="∞";
    drawing.append(generator,grid);
    if (networkState === "fault") drawing.append(svg("path", {d:"M168 2L155 20H169L156 42",stroke:"var(--event)",fill:"none","stroke-width":4}));
    row.append(drawing, node("span", names[networkState])); return row;
  }
  function paint() {
    const run = current(), times = run?.playhead_time_s;
    state.index = Math.min(state.index, times ? times.length-1 : 0);
    const time = times?.[state.index] ?? lab.baseline_config.t_start_s;
    clock.textContent = seconds(time); clock.dataset.timeS = time;
    scrub.max = times ? times.length-1 : 0; scrub.value = state.index;
    scrub.setAttribute("aria-valuetext", seconds(time));
    if (run && state.index === times.length-1) {
      if (state.b) state.observedB = true; else state.observedA = true;
    }
    if (state.compare) state.compared = true;
    root.dataset.comparing = Boolean(state.compare);
    root.dataset.sampleIndex = state.index;
    prompt.textContent = state.transferPending ? state.transferPrompt : !state.a ?
      state.introduction :
      state.transferDone ? "Situación nueva: contrasta tu predicción para C con la evidencia. A conserva la corrida inicial." :
      state.compare ? "Misma máquina y misma falla; solo cambió cuánto duró. Compara el primer movimiento y después busca su causa." :
      "Cambia solo la duración. La corrida anterior conserva su resultado; la nueva necesita tu predicción.";
    const choice = lab.clearing_choices[state.choice];
    const compared = state.c ?? state.b;
    const comparedLabel = state.c ? "C" : "B";
    duration.textContent = state.compare ? `A ${seconds(state.a.fault_duration_s)} · ${comparedLabel} ${seconds(compared.fault_duration_s)}` : seconds(choice.fault_duration_s);
    eventTimes.textContent = state.compare ? `Aplicación: ${seconds(faultTime)} · Despeje A: ${seconds(state.a.evaluation.configuration.network.t_clear_s)} · ${comparedLabel}: ${seconds(compared.evaluation.configuration.network.t_clear_s)}` : `Aplicación: ${seconds(faultTime)} · Despeje absoluto: ${seconds(choice.t_clear_s)}`;
    handle.style.left = `${percent(choice.t_clear_s)}%`;
    handle.setAttribute("aria-valuenow", choice.fault_duration_s);
    handle.setAttribute("aria-valuetext", `Duración ${seconds(choice.fault_duration_s)}; despeje ${seconds(choice.t_clear_s)}`);
    rows.replaceChildren();
    if (state.compare) {
      rows.append(track("A",state.a.evaluation.configuration.network.t_clear_s,"run-a"),track(comparedLabel,compared.evaluation.configuration.network.t_clear_s,"run-b"));
    } else if (state.a && state.observedA) {
      rows.append(track("A",state.a.evaluation.configuration.network.t_clear_s,"run-a"),track("Preparada",choice.t_clear_s,"draft"));
    } else rows.append(track("A",choice.t_clear_s,"run-a"));
    editLayer.classList.toggle("second-row", Boolean(state.a && state.observedA));
    handle.hidden = Boolean(state.compare);
    timeCursor.style.left = `${Math.min(100, percent(time))}%`; timeCursor.hidden = !run || time > eventWindowEnd;
    editNote.textContent = state.compare ? "Las líneas verticales muestran los dos despejes; el cursor comparte el tiempo de ambas corridas." :
      !state.observedA ? "Primero observa la corrida A. Después podrás prolongar la misma falla." :
      state.transferPending ? "Nueva duración sin resultado. Registra tu predicción antes de simular." :
      `Preparada: ${seconds(choice.fault_duration_s)}. Mostrando ${currentLabel()}: ${seconds(current().fault_duration_s)}. Arrastra ↔ o usa las flechas.`;
    editNote.hidden = !state.a;
    markers.replaceChildren(); trails.replaceChildren(); readouts.replaceChildren(); systems.replaceChildren(); balances.replaceChildren();
    // A common presentation scale keeps identical input powers visually equal.
    const powerScale = Math.max(1, ...runs().flatMap(([,item]) => item ? [...item.mechanical_power_pu, ...item.electrical_power_pu].map(Math.abs) : []));
    for (const [label, item] of runs()) {
      const index = state.index;
      const angle = item?.angle_deg[index] ?? lab.initial_angle_deg;
      const group = svg("g", {transform:`rotate(${-angle} 190 132)`, "data-run":label, "data-angle-deg":angle, "data-time-s":item?.evaluation.trajectory.time_s[index] ?? 0});
      const color = label === "A" ? "var(--accent)" : "var(--lab-b)";
      group.append(svg("path", {d:"M190 132H282",stroke:color,"stroke-width":2}));
      group.append(label === "A" ? svg("rect", {x:277,y:127,width:10,height:10,fill:color}) : svg("circle", {cx:282,cy:132,r:9,fill:"none",stroke:color,"stroke-width":2.5}));
      markers.append(group);
      if (item) for (let j = Math.max(0,index-36); j < index; j += 3) {
        trails.append(svg("circle", {cx:282,cy:132,r:2.5,fill:color,opacity:0.2+0.5*(j-Math.max(0,index-36))/36,transform:`rotate(${-item.angle_deg[j]} 190 132)`}));
      }
      const value = node("div", undefined, `run-${label.toLowerCase()}`);
      value.append(node("b", label), node("span", `${item?.relative_turns[index] ?? 0} vueltas completas`));
      if (state.reveal >= 5 && !state.transferPending) value.append(node("span", `δ = ${angle.toFixed(2)}°`));
      readouts.append(value);
      const network = item?.network_state[index] ?? "prefault";
      systems.append(system(label,network));
      if (state.reveal >= 1 && item) {
        const balance = node("div", undefined, `lab-balance run-${label.toLowerCase()}`); balance.dataset.run = label; balance.dataset.timeS = item.evaluation.trajectory.time_s[index];
        balance.append(node("h3", `Corrida ${label} · ${names[network]}`));
        for (const [title, power] of [[state.reveal >= 2 ? "Entrada mecánica · Pm" : "Entrada mecánica",item.mechanical_power_pu[index]], [state.reveal >= 2 ? "Transferencia eléctrica · Pe" : "Transferencia eléctrica",item.electrical_power_pu[index]]]) {
          const line = node("div", undefined, "lab-power"); line.append(node("span", title),node("output",`${power.toFixed(3)} pu`));
          const rail = node("div", undefined, "lab-power-rail"); const bar = node("i");
          const scale = powerScale;
          bar.style.width = `${Math.abs(power)/scale*50}%`; bar.style.left = `${power < 0 ? 50-Math.abs(power)/scale*50 : 50}%`;
          rail.append(bar); line.append(rail); balance.append(line);
        }
        balance.append(node("p", item.cause[index], "lab-causal-text"));
        if (state.reveal >= 3) balance.append(node("p",`Pa = ${item.power_imbalance_pu[index].toFixed(3)} pu`));
        if (state.reveal >= 4) balance.append(node("p",`Δω = ${item.evaluation.trajectory.omega_dev_pu[index].toFixed(6)} pu`));
        balances.append(balance);
      }
    }
    const observationKey = JSON.stringify(runs().map(([label, item]) => [label, item?.network_state[state.index]]));
    if (observation.dataset.key !== observationKey) {
      observation.dataset.key = observationKey; observation.replaceChildren();
      for (const [label, item] of runs()) if (item) {
        const phase = item.network_state[state.index];
        const cue = node("p", `${label} · ${state.lessons[label].observation_cues[phase]}`);
        cue.dataset.run = label; cue.dataset.phase = phase; observation.append(cue);
      }
    }
    observation.hidden = !run;
    reflection.hidden = !state.b || state.transferPending;
    if (state.b) reflectionPrompt.textContent = state.lessons.B.comparison_question;
    causePanel.hidden = state.reveal < 1 || state.reveal === 6 || state.transferPending;
    formal.hidden = true;
    lessonPanel.hidden = state.reveal < 1 || state.transferPending;
    const lesson = state.lessons[currentLabel()];
    if (!lessonPanel.hidden && lesson) {
      const stage = lesson.stages[state.reveal - 1];
      lessonPanel.dataset.stage = stage.id;
      stageTitle.textContent = stage.title; stageText.textContent = stage.text;
      stageQuestion.textContent = stage.question;
    }
    viewTitle.textContent = state.reveal >= 5 && !state.transferPending ? "Ángulo del rotor — δ" : "El generador respecto de la red";
    graph.hidden = !run; closing.hidden = !state.transferDone; scope.hidden = !run;
    if (state.transferDone) closing.textContent = lesson.transfer_reflection;
    if (run) paintPlot();
    // Keep the live region stable during playback; only a new run or selection
    // changes this summary, never every animation frame.
    const resultKey = JSON.stringify([state.compare, state.usedChoices, state.transferPending, state.reveal >= 1]);
    if (resultBox.dataset.key !== resultKey) {
      resultBox.dataset.key = resultKey; resultBox.replaceChildren();
      for (const [label,item] of runs()) if (item) {
        const note = state.lessons[label];
        const card = node("section", undefined, "lab-observation"); card.dataset.run = label;
        card.append(node("h3", `Corrida ${label} · falla de ${seconds(item.fault_duration_s)}`));
        card.append(node("p", `Tu predicción: ${note.prediction}`, "lab-recorded-prediction"));
        const outcome = node("p", outcomes[item.evaluation.first_swing.status] ?? "Resultado no disponible", "lab-outcome");
        outcome.dataset.status = item.evaluation.first_swing.status;
        card.append(outcome, node("p", note.outcome), node("p", note.confrontation, "lab-confrontation"));
        const detail = node("details"); detail.append(node("summary", "Evidencia de esta corrida"),
          node("p", note.evidence), node("p", note.clearing_evidence), node("p", note.why));
        card.append(detail);
        if (state.reveal >= 1 && !state.transferPending) {
          const causal = node("section", undefined, "lab-causal-story");
          causal.append(node("h4", "Cómo se produjo este resultado"));
          for (const step of note.causal_story) {
            const paragraph = node("p", step.text); paragraph.dataset.causalStep = step.id;
            causal.append(paragraph);
          }
          detail.insertBefore(causal, detail.children[1]);
        }
        if (state.compare && label === "A") {
          const prior = node("details", undefined, "lab-prior-result");
          prior.append(node("summary", "A · Ver predicción y evidencia de la corrida inicial"), card);
          resultBox.append(prior);
        } else resultBox.append(card);
      }
    }
    refreshControls();
  }
  function paintPlot() {
    plot.replaceChildren();
    const selected = runs().filter(([,item]) => item);
    const last = state.plotMode === "full" ? current().angle_deg.length - 1 :
      Math.max(...selected.map(([label]) => state.lessons[label].first_swing_end_index));
    const values = selected.flatMap(([,item]) => item.angle_deg.slice(0,last+1));
    const min = Math.min(...values), max = Math.max(...values), span = max-min || 1;
    const start = current().evaluation.trajectory.time_s[0];
    const end = Math.max(...selected.map(([,item]) => item.evaluation.trajectory.time_s[last]));
    const width = Math.max(300, graph.clientWidth - 28), right = width-14, top = 60, bottom = 210;
    plot.setAttribute("viewBox", `0 0 ${width} 260`);
    plot.dataset.startS = start; plot.dataset.endS = end; plot.dataset.mode = state.plotMode;
    plot.dataset.minAngleDeg = min; plot.dataset.maxAngleDeg = max;
    const x = t => 58 + (t-start)/(end-start)*(right-58);
    const y = value => bottom-(value-min)/span*(bottom-top);
    function label(text, tx, ty, anchor = "start") {
      const textNode = svg("text",{x:tx,y:ty,"font-size":12,"text-anchor":anchor,fill:"var(--muted)"});
      textNode.textContent = text; plot.append(textNode);
    }
    plot.append(svg("path",{d:`M58 ${top}V${bottom}H${right}`,fill:"none",stroke:"var(--muted)"}));
    label("Separación angular (°)",58,15);
    for (let i=0;i<=3;i++) {
      const value = min + span*i/3;
      label(value.toFixed(1),50,y(value)+4,"end");
      if (i) plot.append(svg("path",{d:`M58 ${y(value)}H${right}`,stroke:"var(--border)"}));
    }
    label(start.toFixed(3),58,229);
    label(((start+end)/2).toFixed(3),x((start+end)/2),229,"middle");
    label(end.toFixed(3),right,229,"end"); label("Tiempo (s)",right,251,"end");
    for (const [text,time,row,color] of [
      ["Falla",faultTime,0,"var(--event)"],
      ...selected.map(([key,item],i)=>["Despeje "+key,item.evaluation.configuration.network.t_clear_s,i+1,key==="A"?"var(--accent)":"var(--lab-b)"])
    ]) if (time <= end) {
      plot.append(svg("path",{d:`M${x(time)} ${top}V${bottom}`,stroke:color,"stroke-dasharray":"3 4","data-event-time-s":time}));
      label(text,x(time),29+row*13,"middle");
    }
    for (const [key,item] of selected) {
      const color = key === "A" ? "var(--accent)" : "var(--lab-b)";
      const originalTimes = item.evaluation.trajectory.time_s;
      plot.append(svg("polyline",{
        points:item.angle_deg.slice(0,last+1).map((value,i)=>`${x(originalTimes[i])},${y(value)}`).join(" "),
        fill:"none",stroke:color,"stroke-width":2,"data-curve-run":key,"data-sample-count":last+1
      }));
      if (state.index <= last) plot.append(svg("circle",{
        cx:x(originalTimes[state.index]),cy:y(item.angle_deg[state.index]),r:4,fill:color,
        "data-plot-run":key,"data-time-s":originalTimes[state.index]
      }));
    }
    if (state.index <= last) plot.append(svg("path",{
      d:`M${x(current().evaluation.trajectory.time_s[state.index])} ${top}V${bottom}`,
      stroke:"var(--muted)","stroke-dasharray":"4 3"
    }));
    plotNote.textContent = `${state.plotMode === "first" ? "Vista temporal parcial · primera oscilación" : "Trayectoria completa"}: ${seconds(start)}–${seconds(end)}. ${selected.map(([key])=>key).join(" / ")}: misma escala, valores originales en grados; ángulo continuo sin envolver.`;
    cursorNote.hidden = state.index <= last;
    cursorNote.textContent = "El instante seleccionado queda fuera de esta ventana. Usa Trayectoria completa o retrocede el cursor.";
  }
  const resize = new ResizeObserver(() => { if (current()) paintPlot(); });
  resize.observe(graph);
  paint();
  return { destroy() { disposed = true; pause(); resize.disconnect(); } };
}
