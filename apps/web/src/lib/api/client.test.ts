import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHistory } from "./client";

describe("history client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["1M", "3M", "6M", "1Y", "ALL"] as const)(
    "requests the %s timeframe from the synchronized history endpoint",
    async (timeframe) => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ bars: [] }),
      });
      vi.stubGlobal("fetch", fetchMock);

      await fetchHistory("BBCA", timeframe);

      expect(fetchMock).toHaveBeenCalledWith(
        `http://localhost:8000/stocks/BBCA/history?timeframe=${timeframe}`,
        expect.objectContaining({ headers: { Accept: "application/json" } }),
      );
    },
  );
});
