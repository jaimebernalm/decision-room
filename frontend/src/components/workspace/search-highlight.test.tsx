import { expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SearchHighlight } from "./search-highlight";

it.each([
  ["¿Cuántos y cuántas?", "cuant", ["Cuánt", "cuánt"]],
  ["Cafe\u0301 y CAFÉ", "cafe", ["Cafe\u0301", "CAFÉ"]],
  ["Straße", "STRASSE", ["Straße"]],
  ["C++ & 100%_literal", "C++ &", ["C++ &"]],
  ["Sin consulta", "  ", []],
])(
  "preserves original text and highlights literal matches in %s",
  (text, query, matches) => {
    const { container } = render(<SearchHighlight text={text} query={query} />);
    expect(container.textContent).toBe(text);
    expect(
      Array.from(
        container.querySelectorAll("strong"),
        (node) => node.textContent,
      ),
    ).toEqual(matches);
  },
);

it("keeps matching HTML as escaped text", () => {
  const { container } = render(
    <SearchHighlight text={"<img src=x onerror=alert(1)>"} query="img" />,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("strong")).toHaveTextContent("img");
});
