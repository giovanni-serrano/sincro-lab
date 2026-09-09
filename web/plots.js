// Extents and ticks define the viewport; they never produce scientific evidence.
const NS = "http://www.w3.org/2000/svg";
function svgElement(tag, attributes, text) {
  const element = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  if (text !== undefined) element.textContent = text;
  return element;
}

const redrawPlots = new WeakMap();
window.addEventListener("resize", () => {
  for (const holder of document.querySelectorAll(".plots")) redrawPlots.get(holder)?.();
});

export function trajectoryPlots(curves, quantities) {
  const holder = document.createElement("div"); holder.className = "plots";
  function render() {
  const expanded = holder.querySelector("details")?.open ?? false;
  holder.replaceChildren();
  for (const field of ["delta_rad", "omega_dev_pu"]) {
    const metadata = quantities.find(item => item.key === field);
    const title = `${metadata.label} · ${metadata.symbol} (${metadata.unit})`;
    const figure = document.createElement("figure");
    const caption = document.createElement("figcaption"); caption.textContent = title; figure.append(caption);
    const width = Math.max(300, holder.clientWidth - 24 || (window.innerWidth < 600 ? 336 : 736));
    const plot = svgElement("svg", { viewBox:`0 0 ${width} 300`, class:"plot", role:"img", "data-field":field,
      "aria-label":`${title}; muestras calculadas por Python. Datos completos disponibles en el resultado JSON.` });
    let xLow = Infinity, xHigh = -Infinity, yLow = Infinity, yHigh = -Infinity;
    for (const { trajectory } of curves) {
      for (const x of trajectory.time_s) { xLow = Math.min(xLow, x); xHigh = Math.max(xHigh, x); }
      for (const y of trajectory[field]) { yLow = Math.min(yLow, y); yHigh = Math.max(yHigh, y); }
    }
    const xSpan = xHigh - xLow || 1, ySpan = yHigh - yLow || 1;
    const xPixel = x => 72 + (x - xLow) / xSpan * (width - 96);
    const yPixel = y => 245 - (y - yLow) / ySpan * 195;
    for (let tick = 0; tick <= 4; tick++) {
      const y = yLow + ySpan * tick / 4, x = xLow + xSpan * tick / 4;
      plot.append(svgElement("line", { x1:72, x2:width - 24, y1:yPixel(y), y2:yPixel(y), stroke:"var(--border)" }));
      plot.append(svgElement("text", { x:64, y:yPixel(y)+4, "text-anchor":"end", "font-size":13, fill:"var(--muted)" }, y.toPrecision(3)));
      plot.append(svgElement("text", { x:xPixel(x), y:267, "text-anchor":"middle", "font-size":13, fill:"var(--muted)" }, x.toPrecision(3)));
    }
    const events = new Map();
    for (const { configuration } of curves) {
      for (const key of ["t_fault_s", "t_clear_s"]) {
        if (configuration) events.set(`${key}:${configuration.network[key]}`, { key, time:configuration.network[key] });
      }
    }
    let eventIndex = 0;
    for (const { key, time } of events.values()) {
      if (time < xLow || time > xHigh) continue;
      const label = quantities.find(item => item.key === key).label;
      const line = svgElement("line", { x1:xPixel(time), x2:xPixel(time), y1:50, y2:245, stroke:"var(--event)", "stroke-dasharray":"3 4", "data-event":key, "data-time":time });
      line.append(svgElement("title", {}, `${label}: ${time} s`)); plot.append(line);
      // Label placement only; the marker retains the exact configured time.
      plot.append(svgElement("text", { x:72, y:15 + 16 * eventIndex++, "font-size":12, fill:"var(--muted)" }, `${label}: ${time} s`));
    }
    for (const [index, { trajectory }] of curves.entries()) {
      const points = trajectory.time_s.map((time, i) => `${xPixel(time)},${yPixel(trajectory[field][i])}`).join(" ");
      plot.append(svgElement("polyline", { points, fill:"none", stroke:index === 0 && curves.length > 1 ? "var(--muted)" : "var(--accent)", "stroke-width":2, "stroke-dasharray":index === 0 && curves.length > 1 ? "6 4" : "none" }));
    }
    const time = quantities.find(item => item.key === "time_s");
    plot.append(svgElement("text", { x:width / 2, y:295, "text-anchor":"middle", "font-size":13, fill:"var(--muted)" }, `${time.label} (${time.unit})`));
    figure.append(plot);
    if (field === "omega_dev_pu") {
      const detail = document.createElement("details"), summary = document.createElement("summary");
      summary.textContent = "Relacionar el ángulo con la velocidad relativa";
      detail.open = expanded;
      detail.append(summary, figure); holder.append(detail);
    } else holder.append(figure);
  }
  }
  redrawPlots.set(holder, render);
  render();
  requestAnimationFrame(() => { if (holder.isConnected) render(); });
  return holder;
}
