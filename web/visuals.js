// Shared presentation metadata and conceptual assets; no scientific calculations.
export const design = await fetch("./design.json").then(response => {
  if (!response.ok) throw new Error("Presentation assets unavailable");
  return response.json();
});
for (const [key, value] of Object.entries(design.colors)) {
  document.documentElement.style.setProperty(`--${key.replaceAll("_", "-")}`, value);
}

export function diagram(key) {
  const metadata = design.diagrams[key];
  const figure = document.createElement("figure");
  figure.className = "concept-diagram";
  figure.dataset.diagram = key;
  const title = document.createElement("h3"); title.textContent = metadata.title;
  const image = document.createElement("img");
  image.src = `./${metadata.file}`; image.alt = metadata.title;
  image.width = metadata.width; image.height = metadata.height;
  const caption = document.createElement("figcaption"); caption.textContent = metadata.caption;
  figure.append(title, image, caption);
  return figure;
}
