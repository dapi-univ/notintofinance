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
      <p className="surface-state__eyebrow">MARKET DATA</p>
      <strong>{kind === "empty" ? "No history available" : "Chart data unavailable"}</strong>
      <p>{kind === "empty" ? "No market data is available for this symbol." : "The synchronized history payload could not be loaded."}</p>
      {kind === "error" && onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}
