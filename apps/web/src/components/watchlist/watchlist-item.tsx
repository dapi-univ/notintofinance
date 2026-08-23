"use client";

import { memo, useCallback } from "react";

import type { StockListItem } from "@/lib/api/types";
import { formatPrice, formatSigned, marketDirection } from "@/lib/format/market";

import { MiniSparkline } from "./mini-sparkline";

type Props = {
  stock: StockListItem;
  selected: boolean;
  onSelect: (ticker: string) => void;
};

export const WatchlistItem = memo(function WatchlistItem({ stock, selected, onSelect }: Props) {
  const direction = marketDirection(stock.change);
  const available = stock.has_history;
  const handleSelect = useCallback(() => {
    onSelect(stock.ticker);
  }, [onSelect, stock.ticker]);

  return (
    <button
      type="button"
      className={`watchlist-item ${selected ? "watchlist-item--selected" : ""}`}
      onClick={handleSelect}
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
});
