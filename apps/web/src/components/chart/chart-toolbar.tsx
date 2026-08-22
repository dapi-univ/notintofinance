"use client";

import type { ChartType, Timeframe } from "@/lib/chart/adapter";
import type { IndicatorId } from "@/lib/indicators/registry";

import { IndicatorMenu } from "./indicator-menu";

const timeframes: Timeframe[] = ["1M", "3M", "6M", "1Y", "ALL"];

type Props = {
  timeframe: Timeframe;
  onTimeframe: (timeframe: Timeframe) => void;
  chartType: ChartType;
  onChartType: (chartType: ChartType) => void;
  enabledIndicators: Set<IndicatorId>;
  onToggleIndicator: (id: IndicatorId) => void;
};

export function ChartToolbar({ timeframe, onTimeframe, chartType, onChartType, enabledIndicators, onToggleIndicator }: Props) {
  return (
    <div className="chart-toolbar" aria-label="Chart controls">
      <div className="timeframe-selector" role="group" aria-label="Timeframe">
        {timeframes.map((item) => (
          <button key={item} type="button" className={timeframe === item ? "is-active" : ""} aria-pressed={timeframe === item} onClick={() => onTimeframe(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="chart-type-selector" role="group" aria-label="Chart type">
        <button type="button" className={chartType === "candlestick" ? "is-active" : ""} aria-pressed={chartType === "candlestick"} onClick={() => onChartType("candlestick")}>
          Candlestick
        </button>
        <button type="button" className={chartType === "line" ? "is-active" : ""} aria-pressed={chartType === "line"} onClick={() => onChartType("line")}>
          Line
        </button>
      </div>
      <IndicatorMenu enabled={enabledIndicators} onToggle={onToggleIndicator} />
    </div>
  );
}
