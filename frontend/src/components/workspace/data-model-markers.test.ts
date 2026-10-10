import { expect, it } from "vitest";
import { normalizeERMarkers } from "./data-model-markers";

it("preserves optionality, one/many and connection references when normalizing both ends", () => {
  const kinds = ["onlyOne", "zeroOrOne", "oneOrMore", "zeroOrMore"];
  const root = new DOMParser().parseFromString(
    `<svg xmlns="http://www.w3.org/2000/svg"><defs>${kinds
      .flatMap((kind) =>
        ["Start", "End"].map(
          (end) =>
            `<marker class="marker ${kind} er" id="map_${kind}${end}"><path d="M0,18 Q18,0 36,18" /></marker>`,
        ),
      )
      .join(
        "",
      )}</defs><path id="connection" marker-start="url(#map_zeroOrMoreStart)" marker-end="url(#map_zeroOrOneEnd)" /></svg>`,
    "image/svg+xml",
  ).documentElement;
  normalizeERMarkers(root);
  for (const marker of root.querySelectorAll("marker")) {
    const optional =
      marker.classList.contains("zeroOrOne") ||
      marker.classList.contains("zeroOrMore");
    const many =
      marker.classList.contains("oneOrMore") ||
      marker.classList.contains("zeroOrMore");
    expect(marker.querySelectorAll("circle")).toHaveLength(optional ? 1 : 0);
    const drawing = marker.querySelector("path")!.getAttribute("d")!;
    expect(drawing).not.toMatch(/[QC]/);
    // A fork has diagonals; the one side has only vertical bars.
    expect(drawing.includes(",9")).toBe(many);
    expect(marker.getAttribute("markerUnits")).toBe("userSpaceOnUse");
    expect(Number(marker.getAttribute("refX"))).toBe(
      marker.id.endsWith("Start")
        ? 0
        : Number(marker.getAttribute("markerWidth")),
    );
  }
  expect(root.querySelector("#connection")!.getAttribute("marker-start")).toBe(
    "url(#map_zeroOrMoreStart)",
  );
  expect(root.querySelector("#connection")!.getAttribute("marker-end")).toBe(
    "url(#map_zeroOrOneEnd)",
  );
});
