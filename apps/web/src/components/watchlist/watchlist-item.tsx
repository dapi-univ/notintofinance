"use client";

import type { StockListItem } from "@/lib/api/types";
import { formatPrice, formatSigned, marketDirection } from "@/lib/format/market";

import { MiniSparkline } from "./mini-sparkline";

type Props = {
  stock: StockListItem;
  selected: boolean;
  onSelect: (ticker: string) => void;
  onPrefetch: (ticker: string) => void;
};

export function WatchlistItem({ stock, selected, onSelect, onPrefetch }: Props) {
  const direction = marketDirection(stock.change);
  const available = stock.has_history;
  return (
    <button
      type="button"
      className={`watchlist-item ${selected ? "watchlist-item--selected" : ""}`}
      onClick={() => onSelect(stock.ticker)}
      onMouseEnter={() => available && onPrefetch(stock.ticker)}
      onFocus={() => available && onPrefetch(stock.ticker)}
      aria-pressed={selected}
      disabled={!available}
      title={available ? stock.company_name : "History ingestion pending"}
      data-ticker={stock.ticker}
    >
      <span className="watchlist-item__identity">
        <strong>{stock.ticker}</strong>
        <span>{stock.company_name}</span>
      </span>
      <MiniSparkline values={stock.sparkline} direction={direction} />
      <span className="watchlist-item__quote">
        <strong>{formatPrice(stock.latest_close)}</strong>
        <span className={`market-${direction}`}>
          <span aria-hidden="true">{direction === "up" ? "▲" : direction === "down" ? "▼" : "•"}</span>{" "}
          {formatSigned(stock.change_percent)}%
        </span>
      </span>
    </button>
  );
}
