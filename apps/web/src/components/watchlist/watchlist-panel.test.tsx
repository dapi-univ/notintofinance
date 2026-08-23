import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { StockListItem } from "@/lib/api/types";

import {
  getFixedRowVirtualRange,
  WATCHLIST_ROW_HEIGHT,
} from "./fixed-row-virtualizer";
import { WatchlistPanel } from "./watchlist-panel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function createStocks(count: number): StockListItem[] {
  return Array.from({ length: count }, (_, index) => ({
    ticker: `T${index.toString().padStart(3, "0")}`,
    company_name: `Company ${index}`,
    sector: null,
    subsector: null,
    latest_close: 1000 + index,
    change: 10,
    change_percent: 1,
    latest_trade_date: "2026-08-21",
    sparkline: [1000, 1010, 1020],
    has_history: true,
  }));
}

function renderPanel(stocks = createStocks(962)) {
  return render(
    <WatchlistPanel
      stocks={stocks}
      selectedTicker="T000"
      loading={false}
      error={false}
      onRetry={vi.fn()}
      onSelect={vi.fn()}
      onClose={vi.fn()}
    />,
  );
}

describe("fixed-row watchlist virtualization", () => {
  it("bounds a 962-symbol universe to visible rows plus overscan", () => {
    const range = getFixedRowVirtualRange(962, 0, 620);
    expect(range.end - range.start).toBeLessThan(50);

    const { container } = renderPanel();
    expect(container.querySelectorAll(".watchlist-item").length).toBeLessThan(
      50,
    );
    expect(container.querySelectorAll("svg.sparkline").length).toBeLessThan(
      50,
    );
  });

  it("resets virtual scrolling when search changes and reaches lower rows", async () => {
    const { container } = renderPanel();
    const scrollElement = screen.getByTestId("watchlist-scroll");
    scrollElement.scrollTop = 100 * WATCHLIST_ROW_HEIGHT;
    fireEvent.scroll(scrollElement);

    await waitFor(() => {
      expect(container.querySelector('[data-ticker="T100"]')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Search ticker or company"), {
      target: { value: "T900" },
    });

    expect(scrollElement.scrollTop).toBe(0);
    await waitFor(() => {
      expect(container.querySelector('[data-ticker="T900"]')).toBeInTheDocument();
      expect(container.querySelectorAll(".watchlist-item")).toHaveLength(1);
    });
  });

  it("does not fetch history while rows are hovered, focused, or scrolled", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    const { container } = renderPanel();
    const firstRow = container.querySelector<HTMLElement>(".watchlist-item");
    expect(firstRow).not.toBeNull();
    if (firstRow) {
      fireEvent.mouseEnter(firstRow);
      fireEvent.focus(firstRow);
    }
    const scrollElement = screen.getByTestId("watchlist-scroll");
    scrollElement.scrollTop = 20 * WATCHLIST_ROW_HEIGHT;
    fireEvent.scroll(scrollElement);

    await waitFor(() => {
      expect(container.querySelector('[data-ticker="T020"]')).toBeInTheDocument();
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
