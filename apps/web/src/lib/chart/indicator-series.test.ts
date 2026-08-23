import { describe, expect, it, vi } from "vitest";

import type { HistoryBar } from "@/lib/api/types";
import { indicatorDefinitions, type IndicatorId } from "@/lib/indicators/registry";

import { syncIndicatorSeries } from "./indicator-series";

const bars: HistoryBar[] = [
  {
    date: "2026-08-21",
    open: 10,
    high: 12,
    low: 9,
    close: 11,
    previous: 10,
    volume_shares: 3000,
    volume_lots: 30,
    value_idr: 33000,
    frequency: 10,
    frequency_analyzer_raw_shares: 3,
    frequency_analyzer_raw_lots: 0.03,
    foreign_buy_shares: 600,
    foreign_sell_shares: 400,
    foreign_net_shares: 200,
    cumulative_foreign_net_shares: 200,
  },
];

const theme = {
  volumeUp: "rgba(10, 20, 30, 0.58)",
  volumeDown: "rgba(40, 50, 60, 0.54)",
};

class FakeSeries {
  updates: unknown[][] = [];

  setData(data: unknown[]): void {
    this.updates.push(data);
  }
}

describe("generic indicator series lifecycle", () => {
  it("creates, updates, and removes enabled registry series by indicator id", () => {
    const seriesById = new Map<IndicatorId, Map<string, FakeSeries>>();
    const createdIds: string[] = [];
    const removeSeries = vi.fn<(series: FakeSeries) => void>();
    const createSeries = vi.fn((
      definition: (typeof indicatorDefinitions)[number],
      seriesDefinition: (typeof indicatorDefinitions)[number]["rendering"]["series"][number],
    ) => {
      createdIds.push(`${definition.id}:${seriesDefinition.id}`);
      return new FakeSeries();
    });

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume"]),
      theme,
      seriesById,
      createSeries,
      removeSeries,
    });
    const volumeSeries = seriesById.get("volume")?.get("volume");

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume", "frequency-analyzer"]),
      theme,
      seriesById,
      createSeries,
      removeSeries,
    });
    const frequencySeries = seriesById
      .get("frequency-analyzer")
      ?.get("frequency-analyzer");

    expect(createdIds).toEqual([
      "volume:volume",
      "frequency-analyzer:frequency-analyzer",
    ]);
    expect(volumeSeries?.updates).toHaveLength(2);
    expect(volumeSeries?.updates[0]).toEqual([
      { time: "2026-08-21", value: 3000, color: theme.volumeUp },
    ]);
    expect(frequencySeries?.updates[0]).toEqual([
      { time: "2026-08-21", value: Math.log10(3) },
    ]);

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume"]),
      theme,
      seriesById,
      createSeries,
      removeSeries,
    });

    expect(removeSeries).toHaveBeenCalledOnce();
    expect(removeSeries).toHaveBeenCalledWith(frequencySeries);
    expect(seriesById.has("frequency-analyzer")).toBe(false);
    expect(seriesById.get("volume")?.get("volume")).toBe(volumeSeries);
  });

  it("creates all foreign analysis series and removes them as one indicator", () => {
    const seriesById = new Map<IndicatorId, Map<string, FakeSeries>>();
    const removeSeries = vi.fn<(series: FakeSeries) => void>();
    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume", "foreign-analysis"]),
      theme,
      seriesById,
      createSeries: () => new FakeSeries(),
      removeSeries,
    });

    expect(Array.from(seriesById.get("foreign-analysis")?.keys() ?? [])).toEqual([
      "buy",
      "sell",
      "net",
      "cumulative",
    ]);

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume"]),
      theme,
      seriesById,
      createSeries: () => new FakeSeries(),
      removeSeries,
    });

    expect(removeSeries).toHaveBeenCalledTimes(4);
    expect(seriesById.has("foreign-analysis")).toBe(false);
  });
});
