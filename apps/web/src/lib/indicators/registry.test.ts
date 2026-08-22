import { describe, expect, it } from "vitest";

import { indicatorDefinitions, indicatorRegistry } from "./registry";

describe("indicator registry", () => {
  it("is the single source of truth for V0 panes", () => {
    expect(indicatorDefinitions.map((item) => item.id)).toEqual([
      "volume",
      "frequency-analyzer",
    ]);
    expect(indicatorRegistry.volume.defaultVisible).toBe(true);
    expect(indicatorRegistry.volume.category).toBe("market-data");
    expect(indicatorRegistry["frequency-analyzer"].category).toBe("analytics");
    expect(indicatorRegistry["frequency-analyzer"].normalization).toBe(
      "log10(raw shares)",
    );
    expect(indicatorRegistry["frequency-analyzer"].rendering).toMatchObject({
      seriesType: "histogram",
      paneIndex: 2,
      testId: "frequency-analyzer-pane",
    });
  });
});
