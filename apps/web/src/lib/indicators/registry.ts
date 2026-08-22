import type { HistoryBar, Numberish } from "@/lib/api/types";
import { toFrequencyAnalyzer, toVolume } from "@/lib/chart/adapter";
import { formatCompact, toNumber } from "@/lib/format/market";

export type IndicatorId = "volume" | "frequency-analyzer";

export type IndicatorDefinition = {
  id: IndicatorId;
  label: string;
  kind: "pane";
  defaultVisible: boolean;
  requires: Array<keyof HistoryBar>;
  normalization: string | null;
  transform: (bars: HistoryBar[]) => Array<{ time: string; value: number; color?: string }>;
  valueFormatter: (value: Numberish | null) => string;
};

export const indicatorRegistry: Record<IndicatorId, IndicatorDefinition> = {
  volume: {
    id: "volume",
    label: "Volume",
    kind: "pane",
    defaultVisible: true,
    requires: ["volume_shares"],
    normalization: null,
    transform: toVolume,
    valueFormatter: formatCompact,
  },
  "frequency-analyzer": {
    id: "frequency-analyzer",
    label: "Frequency Analyzer",
    kind: "pane",
    defaultVisible: false,
    requires: ["volume_shares", "frequency", "frequency_analyzer_raw_shares"],
    normalization: "log10(raw shares)",
    transform: toFrequencyAnalyzer,
    valueFormatter: (value) => {
      const parsed = toNumber(value);
      return parsed === null ? "—" : parsed.toFixed(4);
    },
  },
};

export const indicatorDefinitions = Object.values(indicatorRegistry);
