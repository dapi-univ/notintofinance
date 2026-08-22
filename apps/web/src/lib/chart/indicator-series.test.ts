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
  },
];

class FakeSeries {
  updates: unknown[][] = [];

  setData(data: unknown[]): void {
    this.updates.push(data);
  }
}

describe("generic indicator series lifecycle", () => {
  it("creates, updates, and removes enabled registry series by indicator id", () => {
    const seriesById = new Map<IndicatorId, FakeSeries>();
    const createdIds: IndicatorId[] = [];
    const removeSeries = vi.fn();
    const createSeries = vi.fn((definition: (typeof indicatorDefinitions)[number]) => {
      createdIds.push(definition.id);
      return new FakeSeries();
    });

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume"]),
      seriesById,
      createSeries,
      removeSeries,
    });
    const volumeSeries = seriesById.get("volume");

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume", "frequency-analyzer"]),
      seriesById,
      createSeries,
      removeSeries,
    });
    const frequencySeries = seriesById.get("frequency-analyzer");

    expect(createdIds).toEqual(["volume", "frequency-analyzer"]);
    expect(volumeSeries?.updates).toHaveLength(2);
    expect(frequencySeries?.updates[0]).toEqual([
      { time: "2026-08-21", value: Math.log10(3) },
    ]);

    syncIndicatorSeries({
      bars,
      definitions: indicatorDefinitions,
      enabled: new Set<IndicatorId>(["volume"]),
      seriesById,
      createSeries,
      removeSeries,
    });

    expect(removeSeries).toHaveBeenCalledOnce();
    expect(removeSeries).toHaveBeenCalledWith(frequencySeries);
    expect(seriesById.has("frequency-analyzer")).toBe(false);
    expect(seriesById.get("volume")).toBe(volumeSeries);
  });
});
