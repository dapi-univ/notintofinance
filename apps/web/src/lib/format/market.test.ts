import { describe, expect, it } from "vitest";

import { formatPrice, formatSigned, marketDirection } from "./market";

describe("market formatting", () => {
  it("formats watchlist values consistently", () => {
    expect(formatPrice("8450")).toBe("8.450");
    expect(formatSigned("1.25")).toBe("+1.25");
    expect(formatSigned("-0.5")).toBe("-0.50");
  });

  it("does not rely only on color for direction", () => {
    expect(marketDirection(2)).toBe("up");
    expect(marketDirection(-2)).toBe("down");
    expect(marketDirection(0)).toBe("flat");
  });
});
