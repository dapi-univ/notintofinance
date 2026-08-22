"use client";

import type { IChartApi, ISeriesApi, SeriesDefinition } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import type { HistoryBar } from "@/lib/api/types";
import { filterBarsByTimeframe, toCandles, type Timeframe } from "@/lib/chart/adapter";
import { syncIndicatorSeries } from "@/lib/chart/indicator-series";
import {
  indicatorDefinitions,
  type IndicatorDefinition,
  type IndicatorId,
} from "@/lib/indicators/registry";

type Props = {
  bars: HistoryBar[];
  timeframe: Timeframe;
  enabledIndicators: ReadonlySet<IndicatorId>;
};

export function MarketChart({ bars, timeframe, enabledIndicators }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const histogramDefinitionRef = useRef<SeriesDefinition<"Histogram"> | null>(null);
  const indicatorSeriesRef = useRef(new Map<IndicatorId, ISeriesApi<"Histogram">>());
  const [ready, setReady] = useState(false);
  const filteredBars = useMemo(() => filterBarsByTimeframe(bars, timeframe), [bars, timeframe]);
  const enabledDefinitions = useMemo(
    () => indicatorDefinitions.filter((definition) => enabledIndicators.has(definition.id)),
    [enabledIndicators],
  );

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
    const indicatorSeries = indicatorSeriesRef.current;
    async function initialize() {
      if (!containerRef.current) return;
      const { CandlestickSeries, ColorType, HistogramSeries, CrosshairMode, createChart } = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;
      const chart = createChart(containerRef.current, {
        autoSize: false,
        layout: {
          background: { type: ColorType.Solid, color: "#11171d" },
          textColor: "#7f8c97",
          fontFamily: "var(--font-ui)",
          fontSize: 11,
          panes: {
            separatorColor: "#27313a",
            separatorHoverColor: "#394650",
            enableResize: true,
          },
        },
        grid: {
          vertLines: { color: "rgba(43, 54, 64, 0.36)" },
          horzLines: { color: "rgba(43, 54, 64, 0.46)" },
        },
        crosshair: { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor: "#2a343d", minimumWidth: 72 },
        timeScale: { borderColor: "#2a343d", timeVisible: false, rightOffset: 4, barSpacing: 7 },
        handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      });
      const candles = chart.addSeries(CandlestickSeries, {
        upColor: "#36b37e",
        downColor: "#eb5757",
        wickUpColor: "#36b37e",
        wickDownColor: "#eb5757",
        borderVisible: false,
        priceLineVisible: true,
        lastValueVisible: true,
      });
      chartRef.current = chart;
      candleRef.current = candles;
      histogramDefinitionRef.current = HistogramSeries;
      observer = new ResizeObserver(() => {
        if (containerRef.current) chart.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);
      });
      observer.observe(containerRef.current);
      setReady(true);
    }
    void initialize();
    return () => {
      disposed = true;
      observer?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      candleRef.current = null;
      histogramDefinitionRef.current = null;
      indicatorSeries.clear();
    };
  }, []);

  useEffect(() => {
    if (!ready || !chartRef.current || !candleRef.current) return;
    candleRef.current.setData(toCandles(filteredBars) as Parameters<typeof candleRef.current.setData>[0]);
    chartRef.current.timeScale().fitContent();
    requestAnimationFrame(() => {
      const panes = chartRef.current?.panes();
      if (panes && panes.length > 1) {
        panes[0].setHeight(Math.max(280, Math.floor((containerRef.current?.clientHeight ?? 600) * 0.68)));
        panes[1].setHeight(120);
      }
    });
  }, [filteredBars, ready]);

  useEffect(() => {
    const chart = chartRef.current;
    const histogramDefinition = histogramDefinitionRef.current;
    if (!ready || !chart || !histogramDefinition) return;

    syncIndicatorSeries({
      bars: filteredBars,
      definitions: indicatorDefinitions,
      enabled: enabledIndicators,
      seriesById: indicatorSeriesRef.current,
      createSeries: (definition: IndicatorDefinition) =>
        chart.addSeries(
          histogramDefinition,
          definition.rendering.options,
          definition.rendering.paneIndex,
        ),
      removeSeries: (series) => chart.removeSeries(series),
    });
  }, [enabledIndicators, filteredBars, ready]);

  return (
    <div className="market-chart" data-testid="market-chart">
      <div className="pane-label pane-label--price">PRICE · IDR</div>
      {enabledDefinitions.map((definition, index) => (
        <div
          key={definition.id}
          className={`pane-label ${definition.rendering.paneLabelClassName} ${
            index < enabledDefinitions.length - 1 ? "pane-label--with-following-pane" : ""
          }`}
          data-testid={definition.rendering.testId}
        >
          {definition.rendering.paneLabel}
        </div>
      ))}
      <div ref={containerRef} className="market-chart__canvas" />
    </div>
  );
}
