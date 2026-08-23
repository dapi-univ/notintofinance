"use client";

import type {
  HistogramSeriesPartialOptions,
  IChartApi,
  ISeriesApi,
  LineSeriesPartialOptions,
  SeriesDefinition,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import type { HistoryBar } from "@/lib/api/types";
import { filterBarsByTimeframe, toCandles, toLine, type ChartType, type Timeframe } from "@/lib/chart/adapter";
import { syncIndicatorSeries } from "@/lib/chart/indicator-series";
import {
  createChartResizeScheduler,
  type ChartResizeScheduler,
} from "@/lib/chart/resize-scheduler";
import { resetTickerViewport } from "@/lib/chart/viewport";
import {
  indicatorDefinitions,
  type IndicatorDefinition,
  type IndicatorId,
  type IndicatorRenderTheme,
  type IndicatorSeriesDefinition,
} from "@/lib/indicators/registry";

type Props = {
  ticker: string;
  bars: HistoryBar[];
  timeframe: Timeframe;
  chartType: ChartType;
  enabledIndicators: ReadonlySet<IndicatorId>;
};

type ChartIndicatorSeries =
  | ISeriesApi<"Histogram">
  | ISeriesApi<"Line">;

function cssColor(styles: CSSStyleDeclaration, token: string, fallback: string): string {
  return styles.getPropertyValue(token).trim() || fallback;
}

function colorWithOpacity(color: string, opacity: number): string {
  const hex = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(color);
  if (hex) {
    const [, red, green, blue] = hex;
    return `rgba(${Number.parseInt(red, 16)}, ${Number.parseInt(green, 16)}, ${Number.parseInt(blue, 16)}, ${opacity})`;
  }

  const rgb = /^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i.exec(color);
  return rgb ? `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${opacity})` : color;
}

export function MarketChart({ ticker, bars, timeframe, chartType, enabledIndicators }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lineRef = useRef<ISeriesApi<"Area"> | null>(null);
  const histogramDefinitionRef = useRef<SeriesDefinition<"Histogram"> | null>(null);
  const lineDefinitionRef = useRef<SeriesDefinition<"Line"> | null>(null);
  const indicatorSeriesRef = useRef(
    new Map<IndicatorId, Map<string, ChartIndicatorSeries>>(),
  );
  const indicatorThemeRef = useRef<IndicatorRenderTheme>({
    volumeUp: "transparent",
    volumeDown: "transparent",
  });
  const paneLabelRefs = useRef(new Map<"price" | IndicatorId, HTMLDivElement>());
  const resizeSchedulerRef = useRef<ChartResizeScheduler | null>(null);
  const paneObserverRef = useRef<ResizeObserver | null>(null);
  const previousTickerRef = useRef(ticker);
  const [ready, setReady] = useState(false);
  const filteredBars = useMemo(() => filterBarsByTimeframe(bars, timeframe), [bars, timeframe]);
  const enabledDefinitions = useMemo(
    () => indicatorDefinitions.filter((definition) => enabledIndicators.has(definition.id)),
    [enabledIndicators],
  );
  const enabledDefinitionsRef = useRef(enabledDefinitions);

  useEffect(() => {
    enabledDefinitionsRef.current = enabledDefinitions;
  }, [enabledDefinitions]);

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
    let paneObserver: ResizeObserver | null = null;
    const indicatorSeries = indicatorSeriesRef.current;
    async function initialize() {
      if (!containerRef.current) return;
      const {
        AreaSeries,
        CandlestickSeries,
        ColorType,
        HistogramSeries,
        LineSeries,
        CrosshairMode,
        createChart,
      } = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;
      const styles = getComputedStyle(document.documentElement);
      const background = cssColor(styles, "--bg-chart", "#141716");
      const text = cssColor(styles, "--text-muted", "#8f8f8f");
      const border = cssColor(styles, "--chart-axis", "#414743");
      const grid = cssColor(styles, "--chart-grid", "rgba(255, 255, 255, 0.045)");
      const separator = cssColor(styles, "--border-muted", "rgba(255, 255, 255, 0.085)");
      const separatorHover = cssColor(styles, "--accent", "#20d978");
      const marketUp = cssColor(styles, "--market-up", "#20d978");
      const marketDown = cssColor(styles, "--market-down", "#ef6a75");
      const accent = cssColor(styles, "--accent", "#20d978");
      indicatorThemeRef.current = {
        volumeUp: colorWithOpacity(marketUp, 0.58),
        volumeDown: colorWithOpacity(marketDown, 0.54),
      };
      const chart = createChart(containerRef.current, {
        autoSize: false,
        layout: {
          background: { type: ColorType.Solid, color: background },
          textColor: text,
          fontFamily: getComputedStyle(document.body).fontFamily,
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
      const line = chart.addSeries(AreaSeries, {
        lineColor: accent,
        lineWidth: 2,
        topColor: colorWithOpacity(accent, 0.18),
        bottomColor: colorWithOpacity(accent, 0.01),
        crosshairMarkerBackgroundColor: accent,
        crosshairMarkerBorderColor: background,
        priceLineColor: colorWithOpacity(accent, 0.55),
        priceLineVisible: true,
        lastValueVisible: true,
        visible: false,
      });
      chartRef.current = chart;
      candleRef.current = candles;
      lineRef.current = line;
      histogramDefinitionRef.current = HistogramSeries;
      lineDefinitionRef.current = LineSeries;
      const updatePaneLabels = () => {
        const container = containerRef.current;
        if (!container) return;
        const containerTop = container.getBoundingClientRect().top;
        const positions = chart.panes().flatMap((pane, index) => {
          const labelId =
            index === 0
              ? "price"
              : enabledDefinitionsRef.current[index - 1]?.id;
          const paneElement = pane.getHTMLElement();
          const label = labelId
            ? paneLabelRefs.current.get(labelId)
            : undefined;
          return paneElement && label
            ? [{ label, top: Math.round(paneElement.getBoundingClientRect().top - containerTop + 8) }]
            : [];
        });
        for (const { label, top } of positions) {
          const nextTop = `${top}px`;
          if (label.style.top !== nextTop) label.style.top = nextTop;
        }
      };
      const resizeScheduler = createChartResizeScheduler({
        chart,
        getAutoScaleSeries: () => [
          candles,
          line,
          ...Array.from(indicatorSeries.values()).flatMap((group) =>
            Array.from(group.values()),
          ),
        ],
        updateLayout: updatePaneLabels,
      });
      resizeSchedulerRef.current = resizeScheduler;
      observer = new ResizeObserver((entries) => {
        const entry = entries.at(-1);
        if (entry) {
          resizeScheduler.scheduleResize(
            entry.contentRect.width,
            entry.contentRect.height,
          );
        }
      });
      observer.observe(containerRef.current);
      paneObserver = new ResizeObserver(() => {
        resizeScheduler.scheduleLayout();
      });
      paneObserverRef.current = paneObserver;
      setReady(true);
    }
    void initialize();
    return () => {
      disposed = true;
      observer?.disconnect();
      paneObserver?.disconnect();
      resizeSchedulerRef.current?.cancel();
      resizeSchedulerRef.current = null;
      paneObserverRef.current = null;
      chartRef.current?.remove();
      chartRef.current = null;
      candleRef.current = null;
      lineRef.current = null;
      histogramDefinitionRef.current = null;
      lineDefinitionRef.current = null;
      indicatorSeries.clear();
    };
  }, []);

  useEffect(() => {
    if (!ready || !chartRef.current || !candleRef.current || !lineRef.current) return;
    candleRef.current.setData(toCandles(filteredBars) as Parameters<typeof candleRef.current.setData>[0]);
    lineRef.current.setData(toLine(filteredBars) as Parameters<typeof lineRef.current.setData>[0]);
    chartRef.current.timeScale().fitContent();
  }, [filteredBars, ready]);

  useEffect(() => {
    if (!ready || !candleRef.current || !lineRef.current) return;
    candleRef.current.applyOptions({ visible: chartType === "candlestick" });
    lineRef.current.applyOptions({ visible: chartType === "line" });
  }, [chartType, ready]);

  useEffect(() => {
    const chart = chartRef.current;
    const histogramDefinition = histogramDefinitionRef.current;
    const lineDefinition = lineDefinitionRef.current;
    if (!ready || !chart || !histogramDefinition || !lineDefinition) return;

    syncIndicatorSeries({
      bars: filteredBars,
      definitions: indicatorDefinitions,
      enabled: enabledIndicators,
      theme: indicatorThemeRef.current,
      seriesById: indicatorSeriesRef.current,
      createSeries: (
        definition: IndicatorDefinition,
        seriesDefinition: IndicatorSeriesDefinition,
      ) => {
        const styles = getComputedStyle(document.documentElement);
        const tokenColor = seriesDefinition.colorToken
          ? cssColor(styles, seriesDefinition.colorToken, "#20d978")
          : undefined;
        const options = tokenColor
          ? { ...seriesDefinition.options, color: tokenColor }
          : seriesDefinition.options;
        const paneIndex = enabledDefinitions.findIndex(
          (item) => item.id === definition.id,
        ) + 1;
        return seriesDefinition.seriesType === "histogram"
          ? chart.addSeries(
              histogramDefinition,
              options as HistogramSeriesPartialOptions,
              paneIndex,
            )
          : chart.addSeries(
              lineDefinition,
              options as LineSeriesPartialOptions,
              paneIndex,
            );
      },
      removeSeries: (series) => chart.removeSeries(series),
    });
  }, [enabledDefinitions, enabledIndicators, filteredBars, ready]);

  useEffect(() => {
    const chart = chartRef.current;
    const candles = candleRef.current;
    const line = lineRef.current;
    if (!ready || !chart || !candles || !line) return;

    resetTickerViewport({
      previousTicker: previousTickerRef.current,
      nextTicker: ticker,
      chart,
      priceSeries: [candles, line],
      indicatorSeries: Array.from(
        indicatorSeriesRef.current.values(),
      ).flatMap((group) => Array.from(group.values())),
    });
    previousTickerRef.current = ticker;
  }, [ready, ticker]);

  useEffect(() => {
    if (!ready) return;
    const frame = requestAnimationFrame(() => {
      const panes = chartRef.current?.panes();
      const height = containerRef.current?.clientHeight ?? 0;
      if (!panes || height === 0 || panes.length < 2) return;
      if (enabledDefinitions.length === 1) {
        panes[0].setHeight(Math.round(height * 0.75));
        panes[1].setHeight(Math.round(height * 0.25));
        resizeSchedulerRef.current?.scheduleLayout();
        return;
      }
      const priceRatio = enabledDefinitions.length === 2 ? 0.67 : 0.62;
      const volumeRatio = enabledDefinitions.length === 2 ? 0.14 : 0.12;
      panes[0].setHeight(Math.round(height * priceRatio));
      panes[1].setHeight(Math.round(height * volumeRatio));
      const remaining = 1 - priceRatio - volumeRatio;
      const analyticsCount = enabledDefinitions.length - 1;
      for (let index = 0; index < analyticsCount; index += 1) {
        panes[index + 2]?.setHeight(
          Math.round((height * remaining) / analyticsCount),
        );
      }
      resizeSchedulerRef.current?.scheduleLayout();
    });
    return () => cancelAnimationFrame(frame);
  }, [enabledDefinitions.length, ready]);

  useEffect(() => {
    if (!ready) return;

    const paneObserver = paneObserverRef.current;
    paneObserver?.disconnect();
    const paneElements = chartRef.current
      ?.panes()
      .map((pane) => pane.getHTMLElement())
      .filter((element): element is HTMLElement => element !== null) ?? [];
    paneElements.forEach((element) => paneObserver?.observe(element));
    resizeSchedulerRef.current?.scheduleLayout();

    return () => paneObserver?.disconnect();
  }, [enabledDefinitions, ready]);

  return (
    <div className="market-chart" data-testid="market-chart">
      <div className="market-chart__pane-labels">
        <div
          ref={(element) => {
            if (element) paneLabelRefs.current.set("price", element);
            else paneLabelRefs.current.delete("price");
          }}
          className="pane-label pane-label--price"
        >
          PRICE · IDR
        </div>
        {enabledDefinitions.map((definition) => (
          <div
            key={definition.id}
            ref={(element) => {
              if (element) paneLabelRefs.current.set(definition.id, element);
              else paneLabelRefs.current.delete(definition.id);
            }}
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
