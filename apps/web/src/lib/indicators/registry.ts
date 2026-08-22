import type { HistogramSeriesPartialOptions } from "lightweight-charts";

import type { HistoryBar, Numberish } from "@/lib/api/types";
import { toFrequencyAnalyzer, toVolume } from "@/lib/chart/adapter";
import { formatCompact, toNumber } from "@/lib/format/market";

export type IndicatorId = "volume" | "frequency-analyzer";
export type IndicatorCategory = "market-data" | "analytics";

export type IndicatorDefinition = {
  id: IndicatorId;
  label: string;
  category: IndicatorCategory;
  kind: "pane";
  defaultVisible: boolean;
  requires: Array<keyof HistoryBar>;
  normalization: string | null;
  transform: (bars: HistoryBar[]) => Array<{ time: string; value: number; color?: string }>;
  valueFormatter: (value: Numberish | null) => string;
  rendering: {
    seriesType: "histogram";
    paneIndex: number;
    paneLabel: string;
    paneLabelClassName: string;
    testId: string;
    options: HistogramSeriesPartialOptions;
    colorToken?: "--accent";
  };
};

export const indicatorGroups: Array<{ id: IndicatorCategory; label: string }> = [
  { id: "market-data", label: "Market Data" },
  { id: "analytics", label: "Analytics" },
];

export const indicatorRegistry: Record<IndicatorId, IndicatorDefinition> = {
  volume: {
    id: "volume",
    label: "Volume",
    category: "market-data",
    kind: "pane",
    defaultVisible: true,
    requires: ["volume_shares"],
    normalization: null,
    transform: toVolume,
    valueFormatter: formatCompact,
    rendering: {
      seriesType: "histogram",
      paneIndex: 1,
      paneLabel: "VOLUME · SHARES",
      paneLabelClassName: "pane-label--volume",
      testId: "volume-pane",
      options: {
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      },
    },
  },
  "frequency-analyzer": {
    id: "frequency-analyzer",
    label: "Frequency Analyzer",
    category: "analytics",
    kind: "pane",
    defaultVisible: false,
    requires: ["volume_shares", "frequency", "frequency_analyzer_raw_shares"],
    normalization: "log10(raw shares)",
    transform: toFrequencyAnalyzer,
    valueFormatter: (value) => {
      const parsed = toNumber(value);
      return parsed === null ? "—" : parsed.toFixed(4);
    },
    rendering: {
      seriesType: "histogram",
      paneIndex: 2,
      paneLabel: "FREQUENCY ANALYZER · LOG10(RAW SHARES)",
      paneLabelClassName: "pane-label--frequency",
      testId: "frequency-analyzer-pane",
      options: {
        priceLineVisible: false,
        lastValueVisible: true,
        priceFormat: { type: "custom", formatter: (value: number) => value.toFixed(2) },
      },
      colorToken: "--accent",
    },
  },
};

export const indicatorDefinitions = Object.values(indicatorRegistry);
