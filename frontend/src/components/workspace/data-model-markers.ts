// Keep Mermaid's relationship semantics and marker IDs, with conventional
// straight crow's feet and a size independent of the selected line's stroke.
export function normalizeERMarkers(root: Element) {
  const ns = "http://www.w3.org/2000/svg";
  for (const marker of root.querySelectorAll("marker.er")) {
    const many =
      marker.classList.contains("zeroOrMore") ||
      marker.classList.contains("oneOrMore");
    const optional =
      marker.classList.contains("zeroOrMore") ||
      marker.classList.contains("zeroOrOne");
    if (!many && !optional && !marker.classList.contains("onlyOne")) continue;
    const start = marker.id.endsWith("Start");
    const width = many ? 40 : 30;
    marker.setAttribute("markerUnits", "userSpaceOnUse");
    marker.setAttribute("viewBox", `0 0 ${width} 18`);
    marker.setAttribute("markerWidth", String(width));
    marker.setAttribute("markerHeight", "18");
    marker.setAttribute("refX", String(start ? 0 : width));
    marker.setAttribute("refY", "9");
    const path = root.ownerDocument.createElementNS(ns, "path");
    const x = start ? (many ? 30 : 20) : 10;
    const maximum = many
      ? start
        ? "M0,2 L18,9 L0,16 M0,9 L18,9"
        : "M40,2 L22,9 L40,16 M22,9 L40,9"
      : start
        ? "M8,2 L8,16"
        : "M22,2 L22,16";
    path.setAttribute("d", maximum + (optional ? "" : ` M${x},2 L${x},16`));
    path.setAttribute("fill", "none");
    marker.replaceChildren(path);
    if (optional) {
      const circle = root.ownerDocument.createElementNS(ns, "circle");
      circle.setAttribute("cx", String(x));
      circle.setAttribute("cy", "9");
      circle.setAttribute("r", "4");
      marker.append(circle);
    }
  }
}
