import { describe, expect, it } from "vitest";

import type { HistoryBar } from "@/lib/api/types";

import { filterBarsByTimeframe, toCandles, toFrequencyAnalyzer } from "./adapter";

const bar = (date: string, raw: number | null = 0.001): HistoryBar => ({
  date,
  open: 10,
  high: 12,
  low: 9,
  close: 11,
  previous: 10,
  volume_shares: 3000,
  volume_lots: 30,
  value_idr: 33000,
  frequency: 10,
  frequency_analyzer_raw_shares: raw,
  frequency_analyzer_raw_lots: raw === null ? null : raw / 100,
});

describe("chart adapter", () => {
  it("keeps every pane on the same date keys", () => {
    const bars = [bar("2026-07-01"), bar("2026-08-01")];
    expect(toCandles(bars).map((item) => item.time)).toEqual(
      toFrequencyAnalyzer(bars).map((item) => item.time),
    );
  });

  it("filters relative to the latest market bar", () => {
    const bars = [bar("2026-01-01"), bar("2026-07-25"), bar("2026-08-21")];
    expect(filterBarsByTimeframe(bars, "1M").map((item) => item.date)).toEqual([
      "2026-07-25",
      "2026-08-21",
    ]);
  });

  it("omits null raw values from the visual transform", () => {
    expect(toFrequencyAnalyzer([bar("2026-08-21", null)])).toEqual([]);
  });
});
