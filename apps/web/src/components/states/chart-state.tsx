"use client";

type Props = {
  kind: "loading" | "empty" | "error";
  onRetry?: () => void;
};

export function ChartState({ kind, onRetry }: Props) {
  if (kind === "loading") {
    return (
      <div className="chart-skeleton" aria-label="Loading chart data">
        <span />
        <span />
        <span />
        <span />
      </div>
    );
  }
  return (
    <div className="surface-state surface-state--chart">
      <p>{kind === "empty" ? "No market data available for this symbol." : "Chart data is unavailable."}</p>
      {kind === "error" && onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}
