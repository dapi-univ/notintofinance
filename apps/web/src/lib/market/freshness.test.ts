import { describe, expect, it } from "vitest";

import { dataStatusLabel } from "./freshness";

describe("data status labels", () => {
  it("prioritizes explicit mock labeling", () => {
    expect(dataStatusLabel(false, true)).toBe("MOCK DATA");
    expect(dataStatusLabel(true, false)).toBe("STALE");
    expect(dataStatusLabel(false, false)).toBe("EOD CURRENT");
  });
});
