"use client";

import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import type { HistoryBar } from "@/lib/api/types";
import { filterBarsByTimeframe, toCandles, type Timeframe } from "@/lib/chart/adapter";
import { indicatorRegistry } from "@/lib/indicators/registry";

type Props = {
  bars: HistoryBar[];
  timeframe: Timeframe;
  frequencyAnalyzerEnabled: boolean;
};

export function MarketChart({ bars, timeframe, frequencyAnalyzerEnabled }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const frequencyRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [ready, setReady] = useState(false);
  const filteredBars = useMemo(() => filterBarsByTimeframe(bars, timeframe), [bars, timeframe]);

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
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
      const volume = chart.addSeries(
        HistogramSeries,
        { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
        1,
      );
      chartRef.current = chart;
      candleRef.current = candles;
      volumeRef.current = volume;
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
      volumeRef.current = null;
      frequencyRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready || !chartRef.current || !candleRef.current || !volumeRef.current) return;
    candleRef.current.setData(toCandles(filteredBars) as Parameters<typeof candleRef.current.setData>[0]);
    volumeRef.current.setData(
      indicatorRegistry.volume.transform(filteredBars) as Parameters<typeof volumeRef.current.setData>[0],
    );
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
    if (!ready || !chartRef.current) return;
    let cancelled = false;
    async function updateFrequencyPane() {
      if (!chartRef.current || cancelled) return;
      if (!frequencyAnalyzerEnabled) {
        if (frequencyRef.current) {
          chartRef.current.removeSeries(frequencyRef.current);
          frequencyRef.current = null;
        }
        return;
      }
      if (!frequencyRef.current) {
        const { LineSeries, LineStyle } = await import("lightweight-charts");
        if (!chartRef.current || cancelled) return;
        frequencyRef.current = chartRef.current.addSeries(
          LineSeries,
          {
            color: "#e0a84b",
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: true,
            priceFormat: { type: "custom", formatter: (value: number) => value.toFixed(2) },
          },
          2,
        );
      }
      frequencyRef.current.setData(
        indicatorRegistry["frequency-analyzer"].transform(filteredBars) as Array<{ time: Time; value: number }>,
      );
    }
    void updateFrequencyPane();
    return () => {
      cancelled = true;
    };
  }, [filteredBars, frequencyAnalyzerEnabled, ready]);

  return (
    <div className="market-chart" data-testid="market-chart">
      <div className="pane-label pane-label--price">PRICE · IDR</div>
      <div
        className={`pane-label pane-label--volume ${frequencyAnalyzerEnabled ? "pane-label--volume-with-fa" : ""}`}
        data-testid="volume-pane"
      >
        VOLUME · SHARES
      </div>
      {frequencyAnalyzerEnabled ? (
        <div className="pane-label pane-label--frequency" data-testid="frequency-analyzer-pane">
          FREQUENCY ANALYZER · LOG10(RAW SHARES)
        </div>
      ) : null}
      <div ref={containerRef} className="market-chart__canvas" />
    </div>
  );
}
