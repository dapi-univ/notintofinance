"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";

import { ChartWorkspace } from "@/components/chart/chart-workspace";
import { NavigationRail } from "@/components/shell/navigation-rail";
import { WatchlistPanel } from "@/components/watchlist/watchlist-panel";
import { useDataStatus, useHistory, useStocks } from "@/lib/api/queries";
import type { Timeframe } from "@/lib/chart/adapter";

const MIN_WATCHLIST = 250;
const MAX_WATCHLIST = 390;

export function DashboardClient({ initialTicker }: { initialTicker: string }) {
  const [activeTicker, setActiveTicker] = useState(initialTicker);
  const [watchlistCollapsed, setWatchlistCollapsed] = useState(false);
  const [watchlistWidth, setWatchlistWidth] = useState(316);
  const [timeframe, setTimeframe] = useState<Timeframe>("6M");
  const [, startTransition] = useTransition();
  const shellRef = useRef<HTMLDivElement>(null);
  const stocks = useStocks();
  const history = useHistory(activeTicker, timeframe);
  const status = useDataStatus();

  const selectTicker = useCallback((ticker: string) => {
    startTransition(() => setActiveTicker(ticker));
    const url = new URL(window.location.href);
    url.searchParams.set("ticker", ticker);
    window.history.replaceState(null, "", url);
  }, []);

  useEffect(() => {
    if (!stocks.data?.length || stocks.data.some((stock) => stock.ticker === activeTicker)) return;
    selectTicker(stocks.data[0].ticker);
  }, [activeTicker, selectTicker, stocks.data]);

  const beginResize = (event: React.PointerEvent<HTMLDivElement>) => {
    const startX = event.clientX;
    const startWidth = watchlistWidth;
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const onMove = (moveEvent: PointerEvent) => {
      setWatchlistWidth(Math.min(MAX_WATCHLIST, Math.max(MIN_WATCHLIST, startWidth + moveEvent.clientX - startX)));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  };

  const resizeWithKeyboard = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setWatchlistWidth((width) => Math.min(MAX_WATCHLIST, Math.max(MIN_WATCHLIST, width + (event.key === "ArrowRight" ? 12 : -12))));
  };

  return (
    <div
      ref={shellRef}
      className={`dashboard-shell ${watchlistCollapsed ? "dashboard-shell--collapsed" : ""}`}
      style={{ "--watchlist-width": `${watchlistWidth}px` } as React.CSSProperties}
    >
      <NavigationRail watchlistCollapsed={watchlistCollapsed} onToggleWatchlist={() => setWatchlistCollapsed((value) => !value)} />
      {!watchlistCollapsed ? (
        <>
          <WatchlistPanel
            stocks={stocks.data ?? []}
            selectedTicker={activeTicker}
            loading={stocks.isLoading}
            error={stocks.isError}
            onRetry={() => void stocks.refetch()}
            onSelect={selectTicker}
            onClose={() => setWatchlistCollapsed(true)}
          />
          <div
            className="watchlist-resizer"
            role="separator"
            aria-label="Resize watchlist"
            aria-orientation="vertical"
            aria-valuemin={MIN_WATCHLIST}
            aria-valuemax={MAX_WATCHLIST}
            aria-valuenow={watchlistWidth}
            tabIndex={0}
            onPointerDown={beginResize}
            onKeyDown={resizeWithKeyboard}
          />
        </>
      ) : null}
      <ChartWorkspace
        ticker={activeTicker}
        history={history.data}
        loading={
          history.isLoading ||
          (history.isFetching && history.data?.ticker !== activeTicker)
        }
        fetching={history.isFetching}
        error={history.isError}
        onRetry={() => void history.refetch()}
        status={status.data}
        timeframe={timeframe}
        onTimeframe={setTimeframe}
      />
    </div>
  );
}
