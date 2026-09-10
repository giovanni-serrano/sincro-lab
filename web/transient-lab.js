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
  let frame = 0, playing = false, disposed = false;
  const root = node("section", undefined, "transient-lab");
  root.id = "transient-lab";
  root.append(node("p", "EXPERIMENTO · UNA MISMA FALLA", "eyebrow"),
    node("h1", "¿Cuánto puede cambiar una fracción de segundo?"));
  const prompt = node("p", undefined, "lab-prompt");
  root.append(prompt);
  const work = node("div", undefined, "lab-work");
  const phenomenon = node("div", undefined, "lab-phenomenon");
  const heading = node("div", undefined, "lab-view-heading");
  const viewTitle = node("h2", "El generador respecto de la red");
  const clock = node("output", "0.000 s", "lab-clock"); clock.id = "lab-time";
  heading.append(viewTitle, clock);
  const angular = svg("svg", { viewBox:"70 32 335 200", role:"img", "aria-label":"Posición del generador respecto de una referencia síncrona fija", class:"lab-angular" });
  const orbit = svg("circle", { cx:190, cy:132, r:92, fill:"none", stroke:"var(--border)", "stroke-width":1 });
  const reference = svg("path", { d:"M190 132H300", stroke:"var(--muted)", "stroke-width":1.5, "stroke-dasharray":"3 4" });
  const referenceText = svg("text", { x:302, y:128, fill:"var(--muted)", "font-size":14 }); referenceText.textContent = "Referencia";
  const referenceText2 = svg("text", { x:302, y:146, fill:"var(--muted)", "font-size":14 }); referenceText2.textContent = "síncrona fija";
  angular.append(orbit, reference, referenceText, referenceText2, svg("circle", {cx:190,cy:132,r:3,fill:"var(--muted)"}));
  const trails = svg("g", {"aria-hidden":"true"});
  const markers = svg("g"); angular.append(trails, markers);
  const readouts = node("div", undefined, "lab-readouts"); readouts.id = "lab-readouts";
  const systems = node("div", undefined, "lab-systems"); systems.id = "lab-systems";
  phenomenon.append(heading, angular, readouts, systems);
  const causePanel = node("aside", undefined, "lab-cause"); causePanel.hidden = true; causePanel.tabIndex = 0; causePanel.setAttribute("aria-label", "Causa y nombres formales");
  causePanel.append(node("h2", "¿Qué impulsa el movimiento?"));
  const balances = node("div"); balances.id = "lab-balances";
  const formal = node("p", undefined, "lab-formal"); formal.hidden = true;
  causePanel.append(balances, formal);
  work.append(phenomenon, causePanel); root.append(work);

  const events = node("section", undefined, "lab-events");
  events.append(node("h2", "Duración de la falla"));
  const timing = node("div", undefined, "lab-timing");
  const duration = node("output"); duration.id = "lab-duration";
  const eventTimes = node("span", undefined, "muted"); eventTimes.id = "lab-event-times";
  timing.append(duration, eventTimes); events.append(timing);
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
  root.append(transport);
  const prediction = node("fieldset", undefined, "lab-prediction"); prediction.id = "lab-prediction";
  prediction.append(node("legend", "Antes de simular, ¿qué crees que ocurrirá?"));
  for (const value of lab.prediction_options) {
    const label = node("label"); const input = node("input");
    input.type = "radio"; input.name = "lab-prediction"; input.value = value; input.checked = state.prediction === value;
    input.addEventListener("change", () => { state.prediction = value; refreshControls(); });
    label.append(input, node("span", predictions[value])); prediction.append(label);
  }
  const run = button("lab-run", "Simular primera corrida", async () => {
    pause();
    await execute(async () => {
      const result = await state.call("transient_lab_run", { clearing_choice_index:state.choice, prediction:state.prediction });
      if (!state.a) state.a = result;
      else { state.b = result; state.observedB = false; }
      state.compare = false; state.compared = false; state.index = 0; state.prediction = ""; state.reveal = 0;
      prediction.querySelectorAll("input").forEach(input => { input.checked = false; });
      paint(); start();
    });
  }); run.className = "primary";
  const experimentActions = node("div", undefined, "lab-experiment-actions"); experimentActions.append(prediction, run);
  root.append(experimentActions);
  const resultBox = node("div", undefined, "lab-result"); resultBox.id = "lab-result"; resultBox.setAttribute("role", "status");
  const revealActions = node("div", undefined, "lab-reveal-actions");
  const compare = button("lab-compare", "Comparar corridas", () => {
    pause(); state.compare = !state.compare; state.index = 0; paint();
  });
  const inspect = button("lab-inspect", "Inspeccionar el primer despeje", () => {
    pause(); state.index = sampleIndex(state.a.playhead_time_s, state.a.evaluation.configuration.network.t_clear_s); paint();
  });
  const revealCause = button("lab-reveal-cause", "Mostrar causa", () => { state.reveal = 1; paint(); });
  const revealAngle = button("lab-reveal-angle", "Dar nombre al ángulo", () => { state.reveal = 2; paint(); });
  const revealPlot = button("lab-reveal-plot", "Ver el movimiento en una gráfica", () => { state.reveal = 3; paint(); });
  revealActions.append(compare, inspect, revealCause, revealAngle, revealPlot);
  root.append(resultBox, revealActions);
  const graph = node("figure", undefined, "lab-graph"); graph.id = "lab-graph"; graph.hidden = true;
  const graphTitle = node("figcaption", "Ángulo del rotor en el tiempo · δ(t)");
  const plot = svg("svg", { viewBox:"0 0 800 240", role:"img", "aria-label":"Ángulo continuo de ambas corridas, con el mismo instante seleccionado" });
  graph.append(graphTitle, plot); root.append(graph);
  const closing = node("p", "Si ambas corridas empiezan igual, ¿por qué despejar la falla no hace que el generador vuelva inmediatamente a su posición inicial?", "lab-closing"); closing.hidden = true;
  const scope = node("p", lab.limitation, "lab-scope"); scope.hidden = true;
  root.append(closing, scope); host.replaceChildren(root);

  function runs() { return state.compare ? [["A", state.a], ["B", state.b]] : [[state.b ? "B" : "A", state.b ?? state.a]]; }
  function current() { return state.b ?? state.a; }
  function pause() { playing = false; cancelAnimationFrame(frame); play.textContent = "Reproducir"; }
  function start() {
    if (!current() || disposed) return;
    pause();
    const times = current().playhead_time_s;
    if (state.index === times.length - 1) state.index = 0;
    playing = true; play.textContent = "Pausar";
    const startWall = performance.now(), startTime = times[state.index];
    function tick(now) {
      if (!playing || disposed) return;
      state.index = sampleIndex(times, startTime + (now - startWall) / 1000 * 0.35);
      paint();
      if (state.index === times.length - 1) pause();
      else frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
  }
  function setChoice(index) {
    if (!state.observedA || state.compare || handle.disabled) return;
    const next = Math.max(0, Math.min(lab.clearing_choices.length - 1, index));
    if (state.choice === next) return;
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
    lock(play, !hasRun); lock(reset, !hasRun); lock(scrub, !hasRun);
    lock(handle, !state.observedA || Boolean(state.compare));
    lock(run, !lab.prediction_options.includes(state.prediction) || Boolean(state.compare) || Boolean(state.a && !state.observedA));
    lock(compare, !state.observedA || !state.observedB);
    inspect.hidden = !state.compare;
    compare.textContent = state.compare ? "Volver a experimentar" : "Comparar corridas";
    revealCause.hidden = !state.compared || state.reveal >= 1;
    revealAngle.hidden = state.reveal !== 1;
    revealPlot.hidden = state.reveal !== 2;
    run.textContent = state.a ? "Simular nueva duración" : "Simular primera corrida";
    prediction.hidden = Boolean(state.compare) || Boolean(state.a && !state.observedA);
    run.hidden = prediction.hidden;
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
    prompt.textContent = !state.a ? "Observa la referencia fija y el generador. Predice qué pasará cuando ocurra la falla." :
      !state.observedA ? "Sigue el movimiento después del despeje. Puedes pausar o recorrer el tiempo." :
      state.compare ? "Dos corridas, el mismo reloj. Recorre el primer despeje para ver dónde cambian sus historias." :
      `Arrastra el final de la región Falla hasta ${seconds(lab.clearing_choices.at(-1).fault_duration_s)}. Predice otra vez y observa qué cambia.`;
    const choice = lab.clearing_choices[state.choice];
    duration.textContent = state.compare ? `A ${seconds(state.a.fault_duration_s)} · B ${seconds(state.b.fault_duration_s)}` : seconds(choice.fault_duration_s);
    eventTimes.textContent = state.compare ? `Aplicación: ${seconds(faultTime)} · Despeje A: ${seconds(state.a.evaluation.configuration.network.t_clear_s)} · B: ${seconds(state.b.evaluation.configuration.network.t_clear_s)}` : `Aplicación: ${seconds(faultTime)} · Despeje absoluto: ${seconds(choice.t_clear_s)}`;
    handle.style.left = `${percent(choice.t_clear_s)}%`;
    handle.setAttribute("aria-valuenow", choice.fault_duration_s);
    handle.setAttribute("aria-valuetext", `Duración ${seconds(choice.fault_duration_s)}; despeje ${seconds(choice.t_clear_s)}`);
    rows.replaceChildren();
    if (state.compare) {
      rows.append(track("A",state.a.evaluation.configuration.network.t_clear_s,"run-a"),track("B",state.b.evaluation.configuration.network.t_clear_s,"run-b"));
    } else if (state.a && state.observedA) {
      rows.append(track("A",state.a.evaluation.configuration.network.t_clear_s,"run-a"),track("Preparada",choice.t_clear_s,"draft"));
    } else rows.append(track("A",choice.t_clear_s,"run-a"));
    editLayer.classList.toggle("second-row", Boolean(state.a && state.observedA));
    handle.hidden = Boolean(state.compare);
    timeCursor.style.left = `${Math.min(100, percent(time))}%`; timeCursor.hidden = !run || time > eventWindowEnd;
    editNote.textContent = state.compare ? "Las líneas verticales muestran los dos despejes; el cursor comparte el tiempo de ambas corridas." :
      !state.observedA ? "Primero observa la corrida A. Después podrás prolongar la misma falla." :
      `Preparada: ${seconds(choice.fault_duration_s)}. ${state.b ? `Mostrando B: ${seconds(state.b.fault_duration_s)}.` : `Mostrando A: ${seconds(state.a.fault_duration_s)}.`} Arrastra ↔ o usa las flechas; Inicio/Fin llevan a los extremos.`;
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
      if (state.reveal >= 2) value.append(node("span", `δ = ${angle.toFixed(2)}°`));
      readouts.append(value);
      const network = item?.network_state[index] ?? "prefault";
      systems.append(system(label,network));
      if (state.reveal >= 1 && item) {
        const balance = node("div", undefined, `lab-balance run-${label.toLowerCase()}`); balance.dataset.run = label; balance.dataset.timeS = item.evaluation.trajectory.time_s[index];
        balance.append(node("h3", `Corrida ${label} · ${names[network]}`));
        for (const [title, power] of [["Entrada mecánica",item.mechanical_power_pu[index]], ["Salida eléctrica",item.electrical_power_pu[index]]]) {
          const line = node("div", undefined, "lab-power"); line.append(node("span", title),node("output",`${power.toFixed(3)} pu`));
          const rail = node("div", undefined, "lab-power-rail"); const bar = node("i");
          const scale = powerScale;
          bar.style.width = `${Math.abs(power)/scale*50}%`; bar.style.left = `${power < 0 ? 50-Math.abs(power)/scale*50 : 50}%`;
          rail.append(bar); line.append(rail); balance.append(line);
        }
        balance.append(node("p", item.cause[index], "lab-causal-text"));
        if (state.reveal >= 2) balance.append(node("p",`Pa = ${item.power_imbalance_pu[index].toFixed(3)} pu`));
        balances.append(balance);
      }
    }
    causePanel.hidden = state.reveal < 1; work.classList.toggle("with-cause",state.reveal >= 1);
    formal.hidden = state.reveal < 2; formal.textContent = run?.formal_explanation ?? "";
    viewTitle.textContent = state.reveal >= 2 ? "Ángulo del rotor — δ" : "El generador respecto de la red";
    graph.hidden = state.reveal < 3; closing.hidden = state.reveal < 3; scope.hidden = !state.observedA;
    if (state.reveal >= 3) paintPlot();
    resultBox.replaceChildren();
    for (const [label,item] of runs()) if (item && (label === "A" ? state.observedA : state.observedB)) {
      const outcome = node("p", `${label} · ${outcomes[item.evaluation.first_swing.status] ?? "Resultado no disponible"}`, "lab-outcome");
      outcome.dataset.status = item.evaluation.first_swing.status; resultBox.append(outcome);
    }
    refreshControls();
  }
  function paintPlot() {
    plot.replaceChildren();
    const selected = runs().filter(([,item]) => item);
    const values = selected.flatMap(([,item]) => item.angle_deg);
    const min = Math.min(...values), max = Math.max(...values), span = max-min || 1;
    const start = current().playhead_time_s[0], end = current().playhead_time_s.at(-1);
    const x = t => 65 + (t-start)/(end-start)*715;
    const y = value => 195-(value-min)/span*170;
    plot.append(svg("path",{d:"M65 20V195H780",fill:"none",stroke:"var(--muted)"}));
    for (const [text,tx,ty] of [[`${max.toFixed(1)}°`,0,30],[`${min.toFixed(1)}°`,0,195],[`${start} s`,65,220],[`${end} s`,755,220]]) {
      const label = svg("text",{x:tx,y:ty,"font-size":14,fill:"var(--muted)"}); label.textContent=text; plot.append(label);
    }
    for (const [label,item] of selected) {
      const color = label === "A" ? "var(--accent)" : "var(--lab-b)";
      plot.append(svg("polyline",{points:item.angle_deg.map((value,i)=>`${x(item.playhead_time_s[i])},${y(value)}`).join(" "),fill:"none",stroke:color,"stroke-width":1.5}));
      plot.append(svg("circle",{cx:x(item.playhead_time_s[state.index]),cy:y(item.angle_deg[state.index]),r:4,fill:color,"data-plot-run":label,"data-time-s":item.evaluation.trajectory.time_s[state.index]}));
    }
    plot.append(svg("path",{d:`M${x(current().playhead_time_s[state.index])} 20V195`,stroke:"var(--muted)","stroke-dasharray":"4 3"}));
  }
  paint();
  return { destroy() { disposed = true; pause(); } };
}
