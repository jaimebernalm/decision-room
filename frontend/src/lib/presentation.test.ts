import { it, expect } from "vitest";
import { presentationNumber } from "./presentation";
it("previews exact large numbers, half-up ties and scientific decimals without float loss", () => {
  expect(presentationNumber("9007199254740993.125", 2)).toBe(
    "9.007.199.254.740.993,13",
  );
  expect(presentationNumber("-0.005", 2)).toBe("-0,01");
  expect(presentationNumber("1.01E+4", 2)).toBe("10.100,00");
  expect(presentationNumber("9.999", 2)).toBe("10,00");
});
