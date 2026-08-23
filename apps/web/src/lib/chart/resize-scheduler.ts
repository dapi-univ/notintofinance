import type { LogicalRange } from "lightweight-charts";

import type { AutoScaleSeries } from "./viewport";

type ResizeChart = {
  resize: (width: number, height: number) => void;
  timeScale: () => {
    getVisibleLogicalRange: () => LogicalRange | null;
    setVisibleLogicalRange: (range: LogicalRange) => void;
  };
};

type FrameRequest = (callback: FrameRequestCallback) => number;
type FrameCancel = (handle: number) => void;

type ResizeSchedulerOptions = {
  chart: ResizeChart;
  getAutoScaleSeries: () => Iterable<AutoScaleSeries>;
  updateLayout: () => void;
  requestFrame?: FrameRequest;
  cancelFrame?: FrameCancel;
};

export type ChartResizeScheduler = {
  scheduleResize: (width: number, height: number) => void;
  scheduleLayout: () => void;
  cancel: () => void;
};

function validRange(range: LogicalRange | null): range is LogicalRange {
  return Boolean(
    range && Number.isFinite(range.from) && Number.isFinite(range.to),
  );
}

export function createChartResizeScheduler({
  chart,
  getAutoScaleSeries,
  updateLayout,
  requestFrame = requestAnimationFrame,
  cancelFrame = cancelAnimationFrame,
}: ResizeSchedulerOptions): ChartResizeScheduler {
  let frame: number | null = null;
  let pendingSize: { width: number; height: number } | null = null;
  let layoutPending = false;
  let lastSize: { width: number; height: number } | null = null;

  const flush = () => {
    frame = null;
    const size = pendingSize;
    const shouldUpdateLayout = layoutPending;
    pendingSize = null;
    layoutPending = false;

    const hasValidSize =
      size &&
      Number.isFinite(size.width) &&
      Number.isFinite(size.height) &&
      size.width > 0 &&
      size.height > 0;
    const changed =
      hasValidSize &&
      (!lastSize ||
        size.width !== lastSize.width ||
        size.height !== lastSize.height);

    if (changed) {
      const visibleRange = chart.timeScale().getVisibleLogicalRange();
      chart.resize(size.width, size.height);
      lastSize = size;
      for (const series of getAutoScaleSeries()) {
        series.priceScale().setAutoScale(true);
      }
      if (validRange(visibleRange)) {
        chart.timeScale().setVisibleLogicalRange(visibleRange);
      }
    }

    if (changed || shouldUpdateLayout) updateLayout();
  };

  const requestFlush = () => {
    if (frame === null) frame = requestFrame(flush);
  };

  return {
    scheduleResize(width, height) {
      pendingSize = {
        width: Math.round(width),
        height: Math.round(height),
      };
      requestFlush();
    },
    scheduleLayout() {
      layoutPending = true;
      requestFlush();
    },
    cancel() {
      if (frame !== null) cancelFrame(frame);
      frame = null;
      pendingSize = null;
      layoutPending = false;
    },
  };
}
