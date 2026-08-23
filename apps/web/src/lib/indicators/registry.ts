import type {
  HistogramSeriesPartialOptions,
  LineSeriesPartialOptions,
} from "lightweight-charts";

import type { HistoryBar, Numberish } from "@/lib/api/types";
import {
  toCumulativeForeignNet,
  toForeignBuy,
  toForeignNet,
  toForeignSell,
  toFrequencyAnalyzer,
  toVolume,
} from "@/lib/chart/adapter";
import { formatCompact, toNumber } from "@/lib/format/market";

export type IndicatorId =
  | "volume"
  | "frequency-analyzer"
  | "foreign-analysis";
export type IndicatorCategory = "market-data" | "analytics";
export type IndicatorRenderTheme = {
  volumeUp: string;
  volumeDown: string;
};
export type IndicatorSeriesType = "histogram" | "line";
export type IndicatorPoint = { time: string; value: number; color?: string };

export type IndicatorSeriesDefinition = {
  id: string;
  seriesType: IndicatorSeriesType;
  transform: (
    bars: HistoryBar[],
    theme: IndicatorRenderTheme,
  ) => IndicatorPoint[];
  options: HistogramSeriesPartialOptions | LineSeriesPartialOptions;
  colorToken?: "--accent" | "--indicator-fa" | "--market-up" | "--market-down";
};

export type IndicatorDefinition = {
  id: IndicatorId;
  label: string;
  category: IndicatorCategory;
  kind: "pane";
  defaultVisible: boolean;
  requires: Array<keyof HistoryBar>;
  normalization: string | null;
  valueFormatter: (value: Numberish | null) => string;
  rendering: {
    paneLabel: string;
    paneLabelClassName: string;
    testId: string;
    series: IndicatorSeriesDefinition[];
  };
};

const volumeFormat = { type: "volume" as const };
const quietSeries = { priceLineVisible: false, lastValueVisible: false };

export const indicatorGroups: Array<{
  id: IndicatorCategory;
  label: string;
}> = [
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
    valueFormatter: formatCompact,
    rendering: {
      paneLabel: "VOLUME · SHARES",
      paneLabelClassName: "pane-label--volume",
      testId: "volume-pane",
      series: [
        {
          id: "volume",
          seriesType: "histogram",
          transform: (bars, theme) =>
            toVolume(bars, { up: theme.volumeUp, down: theme.volumeDown }),
          options: {
            priceFormat: volumeFormat,
            ...quietSeries,
          },
        },
      ],
    },
  },
  "frequency-analyzer": {
    id: "frequency-analyzer",
    label: "Frequency Analyzer",
    category: "analytics",
    kind: "pane",
    defaultVisible: false,
    requires: [
      "volume_shares",
      "frequency",
      "frequency_analyzer_raw_shares",
    ],
    normalization: "log10(raw shares)",
    valueFormatter: (value) => {
      const parsed = toNumber(value);
      return parsed === null ? "—" : parsed.toFixed(4);
    },
    rendering: {
      paneLabel: "FREQUENCY ANALYZER · LOG10(RAW SHARES)",
      paneLabelClassName: "pane-label--frequency",
      testId: "frequency-analyzer-pane",
      series: [
        {
          id: "frequency-analyzer",
          seriesType: "histogram",
          transform: toFrequencyAnalyzer,
          options: {
            priceLineVisible: false,
            lastValueVisible: true,
            priceFormat: {
              type: "custom",
              formatter: (value: number) => value.toFixed(2),
            },
          },
          colorToken: "--indicator-fa",
        },
      ],
    },
  },
  "foreign-analysis": {
    id: "foreign-analysis",
    label: "Foreign Analysis",
    category: "analytics",
    kind: "pane",
    defaultVisible: false,
    requires: [
      "foreign_buy_shares",
      "foreign_sell_shares",
      "foreign_net_shares",
      "cumulative_foreign_net_shares",
    ],
    normalization: "Raw shares · daily and cumulative",
    valueFormatter: formatCompact,
    rendering: {
      paneLabel: "FOREIGN · BUY / SELL / NET / CUMULATIVE SHARES",
      paneLabelClassName: "pane-label--foreign",
      testId: "foreign-analysis-pane",
      series: [
        {
          id: "buy",
          seriesType: "line",
          transform: toForeignBuy,
          options: { ...quietSeries, lineWidth: 1, priceFormat: volumeFormat },
          colorToken: "--market-up",
        },
        {
          id: "sell",
          seriesType: "line",
          transform: toForeignSell,
          options: { ...quietSeries, lineWidth: 1, priceFormat: volumeFormat },
          colorToken: "--market-down",
        },
        {
          id: "net",
          seriesType: "histogram",
          transform: (bars, theme) =>
            toForeignNet(bars, {
              up: theme.volumeUp,
              down: theme.volumeDown,
            }),
          options: { ...quietSeries, priceFormat: volumeFormat },
        },
        {
          id: "cumulative",
          seriesType: "line",
          transform: toCumulativeForeignNet,
          options: {
            priceLineVisible: false,
            lastValueVisible: true,
            lineWidth: 2,
            priceFormat: volumeFormat,
          },
          colorToken: "--accent",
        },
      ],
    },
  },
};

export const indicatorDefinitions = Object.values(indicatorRegistry);
