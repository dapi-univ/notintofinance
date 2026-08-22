"use client";

import type { Timeframe } from "@/lib/chart/adapter";
import type { IndicatorId } from "@/lib/indicators/registry";

import { IndicatorMenu } from "./indicator-menu";

const timeframes: Timeframe[] = ["1M", "3M", "6M", "1Y", "ALL"];

type Props = {
  timeframe: Timeframe;
  onTimeframe: (timeframe: Timeframe) => void;
  enabledIndicators: Set<IndicatorId>;
  onToggleIndicator: (id: IndicatorId) => void;
};

export function ChartToolbar({ timeframe, onTimeframe, enabledIndicators, onToggleIndicator }: Props) {
  return (
    <div className="chart-toolbar" aria-label="Chart controls">
      <div className="timeframe-selector" role="group" aria-label="Timeframe">
        {timeframes.map((item) => (
          <button key={item} type="button" className={timeframe === item ? "is-active" : ""} aria-pressed={timeframe === item} onClick={() => onTimeframe(item)}>
            {item}
          </button>
        ))}
      </div>
      <IndicatorMenu enabled={enabledIndicators} onToggle={onToggleIndicator} />
    </div>
  );
}
