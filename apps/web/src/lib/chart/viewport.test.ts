import { describe, expect, it, vi } from "vitest";

import { resetTickerViewport, type AutoScaleSeries } from "./viewport";

function createSeries() {
  const setAutoScale = vi.fn();
  const series: AutoScaleSeries = {
    priceScale: () => ({ setAutoScale }),
  };
  return { series, setAutoScale };
}

describe("ticker viewport reset", () => {
  it("re-enables autoscale for both price series and every active indicator on ticker change", () => {
    const candle = createSeries();
    const line = createSeries();
    const volume = createSeries();
    const frequencyAnalyzer = createSeries();
    const fitContent = vi.fn();

    const reset = resetTickerViewport({
      previousTicker: "BBCA",
      nextTicker: "ANTM",
      chart: { timeScale: () => ({ fitContent }) },
      priceSeries: [candle.series, line.series],
      indicatorSeries: [volume.series, frequencyAnalyzer.series],
    });

    expect(reset).toBe(true);
    expect(candle.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(line.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(volume.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(frequencyAnalyzer.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(fitContent).toHaveBeenCalledOnce();
  });

  it("preserves the viewport when the ticker identity is unchanged", () => {
    const candle = createSeries();
    const line = createSeries();
    const volume = createSeries();
    const fitContent = vi.fn();

    const reset = resetTickerViewport({
      previousTicker: "BBCA",
      nextTicker: "BBCA",
      chart: { timeScale: () => ({ fitContent }) },
      priceSeries: [candle.series, line.series],
      indicatorSeries: [volume.series],
    });

    expect(reset).toBe(false);
    expect(candle.setAutoScale).not.toHaveBeenCalled();
    expect(line.setAutoScale).not.toHaveBeenCalled();
    expect(volume.setAutoScale).not.toHaveBeenCalled();
    expect(fitContent).not.toHaveBeenCalled();
  });
});
