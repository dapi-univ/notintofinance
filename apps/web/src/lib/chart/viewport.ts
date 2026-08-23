export type AutoScaleSeries = {
  priceScale: () => {
    setAutoScale: (enabled: boolean) => void;
  };
};

type ChartTimeScale = {
  timeScale: () => {
    fitContent: () => void;
  };
};

type ResetTickerViewportOptions = {
  previousTicker: string;
  nextTicker: string;
  chart: ChartTimeScale;
  priceSeries: Iterable<AutoScaleSeries>;
  indicatorSeries: Iterable<AutoScaleSeries>;
};

export function resetTickerViewport({
  previousTicker,
  nextTicker,
  chart,
  priceSeries,
  indicatorSeries,
}: ResetTickerViewportOptions): boolean {
  if (previousTicker === nextTicker) return false;

  for (const series of priceSeries) {
    series.priceScale().setAutoScale(true);
  }
  for (const series of indicatorSeries) {
    series.priceScale().setAutoScale(true);
  }
  chart.timeScale().fitContent();
  return true;
}
