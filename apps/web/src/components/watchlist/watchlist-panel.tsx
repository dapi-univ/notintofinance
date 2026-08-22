"use client";

import { Search, X } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";

import type { StockListItem } from "@/lib/api/types";

import { WatchlistItem } from "./watchlist-item";

type Props = {
  stocks: StockListItem[];
  selectedTicker: string;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  onSelect: (ticker: string) => void;
  onPrefetch: (ticker: string) => void;
  onClose: () => void;
};

export function WatchlistPanel({ stocks, selectedTicker, loading, error, onRetry, onSelect, onPrefetch, onClose }: Props) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());
  const filtered = useMemo(
    () =>
      deferredSearch
        ? stocks.filter(
            (stock) => stock.ticker.toLowerCase().includes(deferredSearch) || stock.company_name.toLowerCase().includes(deferredSearch),
          )
        : stocks,
    [deferredSearch, stocks],
  );

  return (
    <aside className="watchlist" aria-label="Stock watchlist">
      <header className="watchlist__header">
        <div className="product-lockup">
          <h2>NINGGUANG</h2>
          <p>LIYUE SOVEREIGN WEALTH FUND</p>
        </div>
        <div className="watchlist__header-actions">
          <span className="watchlist__market-label">IDX · EOD</span>
          <button className="icon-button watchlist__mobile-close" type="button" aria-label="Close watchlist" onClick={onClose}>
            <X aria-hidden="true" size={16} />
          </button>
        </div>
      </header>
      <label className="watchlist-search">
        <Search aria-hidden="true" size={15} />
        <span className="sr-only">Search watchlist</span>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ticker or company" />
      </label>
      <div className="watchlist__columns" aria-hidden="true">
        <span>SYMBOL</span>
        <span>30D TREND</span>
        <span>LAST / %</span>
      </div>
      <div className="watchlist__rows">
        {loading ? Array.from({ length: 6 }, (_, index) => <div className="watchlist-skeleton" key={index} />) : null}
        {error ? (
          <div className="surface-state surface-state--small">
            <p>Watchlist unavailable.</p>
            <button type="button" onClick={onRetry}>Retry</button>
          </div>
        ) : null}
        {!loading && !error && filtered.length === 0 ? <div className="surface-state surface-state--small"><p>No matching stocks.</p></div> : null}
        {!loading && !error
          ? filtered.map((stock) => (
              <WatchlistItem key={stock.ticker} stock={stock} selected={stock.ticker === selectedTicker} onSelect={onSelect} onPrefetch={onPrefetch} />
            ))
          : null}
      </div>
      <footer className="watchlist__footer">
        <span>{filtered.length} symbols</span>
        <span>EOD</span>
      </footer>
    </aside>
  );
}
