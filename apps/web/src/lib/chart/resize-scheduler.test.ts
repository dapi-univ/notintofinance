import type { LogicalRange } from "lightweight-charts";
import { describe, expect, it, vi } from "vitest";

import { createChartResizeScheduler } from "./resize-scheduler";

function createFrameHarness() {
  let nextId = 1;
  const callbacks = new Map<number, FrameRequestCallback>();
  return {
    requestFrame: vi.fn((callback: FrameRequestCallback) => {
      const id = nextId;
      nextId += 1;
      callbacks.set(id, callback);
      return id;
    }),
    cancelFrame: vi.fn((id: number) => callbacks.delete(id)),
    flush() {
      const queued = Array.from(callbacks.values());
      callbacks.clear();
      queued.forEach((callback) => callback(16));
    },
    queued: () => callbacks.size,
  };
}

function createSeries() {
  const setAutoScale = vi.fn();
  return {
    setAutoScale,
    series: { priceScale: () => ({ setAutoScale }) },
  };
}

describe("chart resize scheduler", () => {
  it("coalesces repeated notifications into one resize and ignores unchanged dimensions", () => {
    const frames = createFrameHarness();
    const resize = vi.fn();
    const updateLayout = vi.fn();
    const timeScale = {
      getVisibleLogicalRange: vi.fn(() => null),
      setVisibleLogicalRange: vi.fn(),
    };
    const scheduler = createChartResizeScheduler({
      chart: { resize, timeScale: () => timeScale },
      getAutoScaleSeries: () => [],
      updateLayout,
      requestFrame: frames.requestFrame,
      cancelFrame: frames.cancelFrame,
    });

    scheduler.scheduleResize(900, 600);
    scheduler.scheduleResize(920, 600);
    scheduler.scheduleResize(940, 600);
    expect(frames.queued()).toBe(1);
    frames.flush();

    expect(resize).toHaveBeenCalledExactlyOnceWith(940, 600);
    expect(updateLayout).toHaveBeenCalledOnce();

    scheduler.scheduleResize(940, 600);
    frames.flush();
    scheduler.scheduleResize(0, 600);
    frames.flush();
    expect(resize).toHaveBeenCalledOnce();
    expect(updateLayout).toHaveBeenCalledOnce();
  });

  it("restores the logical range and re-enables autoscale for price and indicator series", () => {
    const frames = createFrameHarness();
    const candle = createSeries();
    const line = createSeries();
    const volume = createSeries();
    const visibleRange = { from: 12, to: 84 } as LogicalRange;
    const timeScale = {
      getVisibleLogicalRange: vi.fn(() => visibleRange),
      setVisibleLogicalRange: vi.fn(),
    };
    const resize = vi.fn();
    const scheduler = createChartResizeScheduler({
      chart: { resize, timeScale: () => timeScale },
      getAutoScaleSeries: () => [candle.series, line.series, volume.series],
      updateLayout: vi.fn(),
      requestFrame: frames.requestFrame,
      cancelFrame: frames.cancelFrame,
    });

    scheduler.scheduleResize(1100, 700);
    frames.flush();

    expect(resize).toHaveBeenCalledExactlyOnceWith(1100, 700);
    expect(candle.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(line.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(volume.setAutoScale).toHaveBeenCalledExactlyOnceWith(true);
    expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledExactlyOnceWith(
      visibleRange,
    );
  });

  it("cancels queued resize and layout work during cleanup", () => {
    const frames = createFrameHarness();
    const resize = vi.fn();
    const updateLayout = vi.fn();
    const scheduler = createChartResizeScheduler({
      chart: {
        resize,
        timeScale: () => ({
          getVisibleLogicalRange: () => null,
          setVisibleLogicalRange: vi.fn(),
        }),
      },
      getAutoScaleSeries: () => [],
      updateLayout,
      requestFrame: frames.requestFrame,
      cancelFrame: frames.cancelFrame,
    });

    scheduler.scheduleResize(800, 500);
    scheduler.scheduleLayout();
    scheduler.cancel();
    frames.flush();

    expect(frames.cancelFrame).toHaveBeenCalledOnce();
    expect(resize).not.toHaveBeenCalled();
    expect(updateLayout).not.toHaveBeenCalled();
  });
});
