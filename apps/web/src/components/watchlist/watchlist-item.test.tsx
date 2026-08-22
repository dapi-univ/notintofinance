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
        onPrefetch={() => undefined}
        stock={{
          ticker: "ANTM",
          company_name: "Aneka Tambang Tbk.",
          sector: null,
          latest_close: 3150,
          change: 30,
          change_percent: 0.96,
          latest_trade_date: "2026-08-21",
          sparkline: [3000, 3040, 3150],
        }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /ANTM/i }));
    expect(onSelect).toHaveBeenCalledWith("ANTM");
    expect(screen.getByText("▲")).toBeInTheDocument();
  });
});
