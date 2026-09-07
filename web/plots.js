// Map source samples to SVG coordinates only. Extents define the viewport;
// they are never reported as scientific metrics or used for classification.
const NS = "http://www.w3.org/2000/svg";
function svgElement(tag, attributes, text) {
  const element = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  if (text !== undefined) element.textContent = text;
  return element;
}

export function trajectoryPlots(curves) {
  const holder = document.createElement("div");
  holder.className = "plots";
  for (const [field, title] of [["delta_rad", "Ángulo del rotor · rad"], ["omega_dev_pu", "Desviación de velocidad · pu"]]) {
    const figure = document.createElement("figure");
    const caption = document.createElement("figcaption");
    caption.textContent = title;
    figure.append(caption);
    const width = window.innerWidth < 600 ? 360 : 540;
    const plot = svgElement("svg", { viewBox: `0 0 ${width} 290`, class: "plot", role: "img", "aria-label": `${title}; muestras calculadas por Python. Datos completos disponibles en el resultado JSON.` });
    let xLow = Infinity, xHigh = -Infinity, yLow = Infinity, yHigh = -Infinity;
    for (const { trajectory } of curves) {
      for (const x of trajectory.time_s) { xLow = Math.min(xLow, x); xHigh = Math.max(xHigh, x); }
      for (const y of trajectory[field]) { yLow = Math.min(yLow, y); yHigh = Math.max(yHigh, y); }
    }
    const xSpan = xHigh - xLow || 1;
    const ySpan = yHigh - yLow || 1;
    const xPixel = x => 72 + (x - xLow) / xSpan * (width - 96);
    const yPixel = y => 239 - (y - yLow) / ySpan * 205;
    for (let tick = 0; tick <= 4; tick++) {
      const y = yLow + ySpan * tick / 4;
      const x = xLow + xSpan * tick / 4;
      plot.append(svgElement("line", { x1:72, x2:width - 24, y1:yPixel(y), y2:yPixel(y), stroke:"#e2e8ec" }));
      plot.append(svgElement("text", { x:64, y:yPixel(y)+4, "text-anchor":"end", "font-size":14, fill:"#526776" }, y.toPrecision(3)));
      plot.append(svgElement("text", { x:xPixel(x), y:260, "text-anchor":"middle", "font-size":14, fill:"#526776" }, x.toPrecision(3)));
    }
    for (const [index, { trajectory }] of curves.entries()) {
      const points = trajectory.time_s.map((time, i) => `${xPixel(time)},${yPixel(trajectory[field][i])}`).join(" ");
      plot.append(svgElement("polyline", { points, fill:"none", stroke: index === 0 && curves.length > 1 ? "#607784" : "#08688a", "stroke-width":2, "stroke-dasharray":index === 0 && curves.length > 1 ? "6 4" : "none" }));
    }
    plot.append(svgElement("text", { x:width / 2, y:285, "text-anchor":"middle", "font-size":14, fill:"#526776" }, "Tiempo · s"));
    figure.append(plot);
    holder.append(figure);
  }
  return holder;
}
