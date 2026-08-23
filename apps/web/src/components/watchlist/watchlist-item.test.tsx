import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WatchlistItem } from "./watchlist-item";

describe("WatchlistItem", () => {
  it("selects a ticker without relying on a page navigation", () => {
    const onSelect = vi.fn();
    render(
      <WatchlistItem
        selected={false}
        onSelect={onSelect}
        stock={{
          ticker: "ANTM",
          company_name: "Aneka Tambang Tbk.",
          sector: null,
          subsector: null,
          latest_close: 3150,
          change: 30,
          change_percent: 0.96,
          latest_trade_date: "2026-08-21",
          sparkline: [3000, 3040, 3150],
          has_history: true,
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /ANTM/i }));
    expect(onSelect).toHaveBeenCalledWith("ANTM");
    expect(screen.getByText("▲")).toBeInTheDocument();
  });

  it("keeps partial-universe symbols visible but unavailable until history exists", () => {
    const onSelect = vi.fn();
    render(
      <WatchlistItem
        selected={false}
        onSelect={onSelect}
        stock={{
          ticker: "ZZZZ",
          company_name: "History Pending",
          sector: null,
          subsector: null,
          latest_close: null,
          change: null,
          change_percent: null,
          latest_trade_date: null,
          sparkline: [],
          has_history: false,
        }}
      />,
    );

    const button = screen.getByRole("button", { name: /ZZZZ/i });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
