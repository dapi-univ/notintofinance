"use client";

import { RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import type { HistoryResponse } from "@/lib/api/types";
import type { Timeframe } from "@/lib/chart/adapter";
import { dataStatusLabel } from "@/lib/market/freshness";
import type { IndicatorId } from "@/lib/indicators/registry";

import { ChartState } from "@/components/states/chart-state";
import { ChartToolbar } from "./chart-toolbar";
import { MarketChart } from "./market-chart";
import { SymbolHeader } from "./symbol-header";

type Props = {
  ticker: string;
  history: HistoryResponse | undefined;
  loading: boolean;
  fetching: boolean;
  error: boolean;
  onRetry: () => void;
  status: { latest_trade_date: string | null; is_stale: boolean; is_mock: boolean } | undefined;
  timeframe: Timeframe;
  onTimeframe: (timeframe: Timeframe) => void;
};

export function ChartWorkspace({ ticker, history, loading, fetching, error, onRetry, status, timeframe, onTimeframe }: Props) {
  const [enabledIndicators, setEnabledIndicators] = useState<Set<IndicatorId>>(
    () => new Set<IndicatorId>(["volume"]),
  );
  const validHistory = history?.ticker === ticker ? history : undefined;
  const hasData = Boolean(validHistory?.bars.length);
  const toggleIndicator = (id: IndicatorId) => {
    if (id === "volume") return;
    setEnabledIndicators((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const statusText = useMemo(
    () => (status ? dataStatusLabel(status.is_stale, status.is_mock) : "CHECKING"),
    [status],
  );
  const statusMode = status?.is_mock ? "mock" : status?.is_stale ? "stale" : "current";

  return (
    <main className="chart-workspace">
      <SymbolHeader ticker={ticker} history={validHistory} loading={loading || fetching} />
      <div className="workspace-control-row">
        <ChartToolbar timeframe={timeframe} onTimeframe={onTimeframe} enabledIndicators={enabledIndicators} onToggleIndicator={toggleIndicator} />
        <div className="data-freshness" data-status={statusMode}>
          <span className="data-freshness__dot" />
          <strong>{statusText}</strong>
          <span className="data-freshness__date">AS OF {status?.latest_trade_date ?? "NO TRADE DATE"}</span>
        </div>
      </div>
      <section className="chart-stage" aria-label={`${ticker} synchronized price and indicator chart`}>
        {loading ? <ChartState kind="loading" /> : null}
        {error ? <ChartState kind="error" onRetry={onRetry} /> : null}
        {!loading && !error && !hasData ? <ChartState kind="empty" /> : null}
        {!loading && !error && hasData && validHistory ? (
          <MarketChart bars={validHistory.bars} timeframe={timeframe} enabledIndicators={enabledIndicators} />
        ) : null}
        {fetching && hasData ? (
          <div className="chart-refresh" role="status"><RefreshCw aria-hidden="true" size={13} /> Updating {ticker}</div>
        ) : null}
      </section>
      <footer className="workspace-footer">
        <span>Source: {validHistory?.source?.toUpperCase() ?? "—"}</span>
        <span>Volume stored in shares · Lots = shares / 100</span>
        <span>FA raw = Volume / Frequency³</span>
      </footer>
    </main>
  );
}
