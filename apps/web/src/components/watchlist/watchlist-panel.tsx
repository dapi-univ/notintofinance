"use client";

import { Search, X } from "lucide-react";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { StockListItem } from "@/lib/api/types";

import { WatchlistItem } from "./watchlist-item";
import {
  getFixedRowVirtualRange,
  WATCHLIST_INITIAL_VIEWPORT_HEIGHT,
  WATCHLIST_ROW_HEIGHT,
} from "./fixed-row-virtualizer";

type Props = {
  stocks: StockListItem[];
  selectedTicker: string;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  onSelect: (ticker: string) => void;
  onClose: () => void;
};

export function WatchlistPanel({ stocks, selectedTicker, loading, error, onRetry, onSelect, onClose }: Props) {
  const [search, setSearch] = useState("");
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(
    WATCHLIST_INITIAL_VIEWPORT_HEIGHT,
  );
  const rowsRef = useRef<HTMLDivElement>(null);
  const scrollFrameRef = useRef<number | null>(null);
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
  const readyCount = useMemo(
    () => filtered.filter((stock) => stock.has_history).length,
    [filtered],
  );
  const virtualRange = useMemo(
    () =>
      getFixedRowVirtualRange(
        filtered.length,
        scrollTop,
        viewportHeight,
      ),
    [filtered.length, scrollTop, viewportHeight],
  );
  const virtualStocks = filtered.slice(virtualRange.start, virtualRange.end);

  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const element = event.currentTarget;
    if (scrollFrameRef.current !== null) return;
    scrollFrameRef.current = requestAnimationFrame(() => {
      scrollFrameRef.current = null;
      setScrollTop(element.scrollTop);
    });
  }, []);

  const handleSearch = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    if (rowsRef.current) rowsRef.current.scrollTop = 0;
    setScrollTop(0);
  }, []);

  useEffect(() => {
    const element = rowsRef.current;
    if (!element) return;
    const updateHeight = (height: number) => {
      if (height > 0) setViewportHeight(Math.round(height));
    };
    updateHeight(element.clientHeight);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries.at(-1);
      if (entry) updateHeight(entry.contentRect.height);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(
    () => () => {
      if (scrollFrameRef.current !== null) {
        cancelAnimationFrame(scrollFrameRef.current);
      }
    },
    [],
  );

  return (
    <aside className="watchlist" aria-label="Stock watchlist">
      <header className="watchlist__header">
        <div className="product-lockup">
          <h2>KEJORA</h2>
          <p>Equity Research Tools</p>
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
        <input value={search} onChange={handleSearch} placeholder="Search ticker or company" />
      </label>
      <div className="watchlist__columns" aria-hidden="true">
        <span>SYMBOL</span>
        <span>30D TREND</span>
        <span>LAST / %</span>
      </div>
      <div
        ref={rowsRef}
        className="watchlist__rows"
        data-testid="watchlist-scroll"
        onScroll={handleScroll}
      >
        {loading ? Array.from({ length: 6 }, (_, index) => <div className="watchlist-skeleton" key={index} />) : null}
        {error ? (
          <div className="surface-state surface-state--small">
            <p>Watchlist unavailable.</p>
            <button type="button" onClick={onRetry}>Retry</button>
          </div>
        ) : null}
        {!loading && !error && filtered.length === 0 ? <div className="surface-state surface-state--small"><p>No matching stocks.</p></div> : null}
        {!loading && !error && filtered.length > 0 ? (
          <div
            className="watchlist-virtual-space"
            style={{ height: `${virtualRange.totalHeight}px` }}
            role="list"
            aria-label={`${filtered.length} watchlist symbols`}
          >
            {virtualStocks.map((stock, index) => {
              const absoluteIndex = virtualRange.start + index;
              return (
                <div
                  key={stock.ticker}
                  className="watchlist-virtual-row"
                  style={{ transform: `translateY(${absoluteIndex * WATCHLIST_ROW_HEIGHT}px)` }}
                  role="listitem"
                  aria-posinset={absoluteIndex + 1}
                  aria-setsize={filtered.length}
                >
                  <WatchlistItem
                    stock={stock}
                    selected={stock.ticker === selectedTicker}
                    onSelect={onSelect}
                  />
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
      <footer className="watchlist__footer">
        <span>{readyCount} ready · {filtered.length} symbols</span>
        <span>EOD</span>
      </footer>
    </aside>
  );
}
