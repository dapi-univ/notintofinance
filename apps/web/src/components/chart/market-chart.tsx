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

function cssColor(styles: CSSStyleDeclaration, token: string, fallback: string): string {
  return styles.getPropertyValue(token).trim() || fallback;
}

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
      const styles = getComputedStyle(document.documentElement);
      const background = cssColor(styles, "--bg-chart", "#101416");
      const text = cssColor(styles, "--text-muted", "#737a78");
      const border = cssColor(styles, "--chart-axis", "#303736");
      const grid = cssColor(styles, "--chart-grid", "rgba(112, 120, 116, 0.1)");
      const separator = cssColor(styles, "--border-subtle", "#262c2c");
      const separatorHover = cssColor(styles, "--border-active", "#78613a");
      const marketUp = cssColor(styles, "--market-up", "#4f9f7d");
      const marketDown = cssColor(styles, "--market-down", "#c25b56");
      const chart = createChart(containerRef.current, {
        autoSize: false,
        layout: {
          background: { type: ColorType.Solid, color: background },
          textColor: text,
          fontFamily: "var(--font-ui)",
          fontSize: 11,
          panes: {
            separatorColor: separator,
            separatorHoverColor: separatorHover,
            enableResize: true,
          },
        },
        grid: {
          vertLines: { color: grid },
          horzLines: { color: grid },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: border, labelBackgroundColor: separatorHover },
          horzLine: { color: border, labelBackgroundColor: separatorHover },
        },
        rightPriceScale: { borderColor: border, minimumWidth: 72 },
        timeScale: { borderColor: border, timeVisible: false, rightOffset: 4, barSpacing: 7 },
        handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
      });
      const candles = chart.addSeries(CandlestickSeries, {
        upColor: marketUp,
        downColor: marketDown,
        wickUpColor: marketUp,
        wickDownColor: marketDown,
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
      createSeries: (definition: IndicatorDefinition) => {
        const styles = getComputedStyle(document.documentElement);
        const tokenColor = definition.rendering.colorToken
          ? cssColor(styles, definition.rendering.colorToken, "#b89554")
          : undefined;
        return chart.addSeries(
          histogramDefinition,
          tokenColor
            ? { ...definition.rendering.options, color: tokenColor }
            : definition.rendering.options,
          definition.rendering.paneIndex,
        );
      },
      removeSeries: (series) => chart.removeSeries(series),
    });
  }, [enabledIndicators, filteredBars, ready]);

  useEffect(() => {
    if (!ready) return;
    const frame = requestAnimationFrame(() => {
      const panes = chartRef.current?.panes();
      const height = containerRef.current?.clientHeight ?? 0;
      if (!panes || height === 0 || panes.length < 2) return;
      if (enabledDefinitions.length === 1) {
        panes[0].setHeight(Math.round(height * 0.75));
        panes[1].setHeight(Math.round(height * 0.25));
        return;
      }
      panes[0].setHeight(Math.round(height * 0.67));
      panes[1].setHeight(Math.round(height * 0.14));
      panes[2]?.setHeight(Math.round(height * 0.19));
    });
    return () => cancelAnimationFrame(frame);
  }, [enabledDefinitions.length, ready]);

  return (
    <div className={`market-chart ${enabledDefinitions.length > 1 ? "market-chart--with-fa" : ""}`} data-testid="market-chart">
      <div className="market-chart__pane-labels">
        <div className="pane-label pane-label--price">PRICE · IDR</div>
        {enabledDefinitions.map((definition) => (
          <div
            key={definition.id}
            className={`pane-label ${definition.rendering.paneLabelClassName}`}
            data-testid={definition.rendering.testId}
          >
            {definition.rendering.paneLabel}
          </div>
        ))}
      </div>
      <div ref={containerRef} className="market-chart__canvas" />
    </div>
  );
}
