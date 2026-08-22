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
  type IndicatorRenderTheme,
} from "@/lib/indicators/registry";

type Props = {
  bars: HistoryBar[];
  timeframe: Timeframe;
  enabledIndicators: ReadonlySet<IndicatorId>;
};

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

export function MarketChart({ bars, timeframe, enabledIndicators }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const histogramDefinitionRef = useRef<SeriesDefinition<"Histogram"> | null>(null);
  const indicatorSeriesRef = useRef(new Map<IndicatorId, ISeriesApi<"Histogram">>());
  const indicatorThemeRef = useRef<IndicatorRenderTheme>({
    volumeUp: "transparent",
    volumeDown: "transparent",
  });
  const paneLabelRefs = useRef(new Map<"price" | IndicatorId, HTMLDivElement>());
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
      indicatorThemeRef.current = {
        volumeUp: colorWithOpacity(marketUp, 0.58),
        volumeDown: colorWithOpacity(marketDown, 0.54),
      };
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
      theme: indicatorThemeRef.current,
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

  useEffect(() => {
    if (!ready) return;

    let frame = 0;
    let paneObserver: ResizeObserver | null = null;
    const updatePaneLabels = () => {
      const chart = chartRef.current;
      const container = containerRef.current;
      if (!chart || !container) return;
      const containerTop = container.getBoundingClientRect().top;

      chart.panes().forEach((pane, index) => {
        const labelId = index === 0 ? "price" : enabledDefinitions[index - 1]?.id;
        const paneElement = pane.getHTMLElement();
        const label = labelId ? paneLabelRefs.current.get(labelId) : undefined;
        if (!paneElement || !label) return;
        label.style.top = `${Math.round(paneElement.getBoundingClientRect().top - containerTop + 8)}px`;
      });
    };

    frame = requestAnimationFrame(() => {
      const paneElements = chartRef.current
        ?.panes()
        .map((pane) => pane.getHTMLElement())
        .filter((element): element is HTMLElement => element !== null) ?? [];
      paneObserver = new ResizeObserver(updatePaneLabels);
      paneElements.forEach((element) => paneObserver?.observe(element));
      updatePaneLabels();
    });

    return () => {
      cancelAnimationFrame(frame);
      paneObserver?.disconnect();
    };
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
