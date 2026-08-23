import { describe, expect, it } from "vitest";

import { indicatorDefinitions, indicatorRegistry } from "./registry";

describe("indicator registry", () => {
  it("is the single source of truth for operational EOD panes", () => {
    expect(indicatorDefinitions.map((item) => item.id)).toEqual([
      "volume",
      "frequency-analyzer",
      "foreign-analysis",
      "broker-accumulation",
    ]);
    expect(indicatorRegistry.volume.defaultVisible).toBe(true);
    expect(indicatorRegistry.volume.category).toBe("market-data");
    expect(indicatorRegistry["frequency-analyzer"].category).toBe("analytics");
    expect(indicatorRegistry["frequency-analyzer"].normalization).toBe(
      "log10(raw shares)",
    );
    expect(indicatorRegistry["frequency-analyzer"].rendering).toMatchObject({
      testId: "frequency-analyzer-pane",
    });
    expect(
      indicatorRegistry["frequency-analyzer"].rendering.series[0].seriesType,
    ).toBe("histogram");
    expect(
      indicatorRegistry["foreign-analysis"].rendering.series.map(
        (series) => series.id,
      ),
    ).toEqual(["buy", "sell", "net", "cumulative"]);
    expect(indicatorRegistry["broker-accumulation"]).toMatchObject({
      kind: "workspace",
      defaultVisible: false,
    });
  });
});
