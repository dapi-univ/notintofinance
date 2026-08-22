import type { HistoryBar } from "@/lib/api/types";
import { toNumber } from "@/lib/format/market";

export type Timeframe = "1M" | "3M" | "6M" | "1Y" | "ALL";

const timeframeDays: Record<Exclude<Timeframe, "ALL">, number> = {
  "1M": 31,
  "3M": 93,
  "6M": 186,
  "1Y": 366,
};

export function filterBarsByTimeframe(bars: HistoryBar[], timeframe: Timeframe): HistoryBar[] {
  if (timeframe === "ALL" || bars.length === 0) return bars;
  const latest = new Date(`${bars[bars.length - 1].date}T00:00:00Z`);
  const cutoff = new Date(latest);
  cutoff.setUTCDate(cutoff.getUTCDate() - timeframeDays[timeframe]);
  return bars.filter((bar) => new Date(`${bar.date}T00:00:00Z`) >= cutoff);
}

export function toCandles(bars: HistoryBar[]) {
  return bars.map((bar) => ({
    time: bar.date,
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
  }));
}

export function toVolume(bars: HistoryBar[]) {
  return bars.map((bar) => ({
    time: bar.date,
    value: bar.volume_shares,
    color: Number(bar.close) >= Number(bar.open) ? "rgba(54, 179, 126, 0.58)" : "rgba(235, 87, 87, 0.52)",
  }));
}

export function toFrequencyAnalyzer(bars: HistoryBar[]) {
  return bars.flatMap((bar) => {
    const raw = toNumber(bar.frequency_analyzer_raw_shares);
    if (raw === null || raw <= 0) return [];
    return [{ time: bar.date, value: Math.log10(raw) }];
  });
}
