import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchBrokerAccumulation, fetchHistory } from "./client";

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

describe("broker accumulation client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads only the FastAPI broker-accumulation contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ brokers: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchBrokerAccumulation("BBCA", "2026-08-01", "2026-08-21");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/stocks/BBCA/broker-accumulation?from=2026-08-01&to=2026-08-21",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("retains sanitized FastAPI status, detail, and body diagnostics", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () =>
        JSON.stringify({
          detail: "Broker-accumulation range is invalid",
          token: "test-secret-value",
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const error = await fetchBrokerAccumulation(
      "BBCA",
      "2026-08-21",
      "2026-08-07",
    ).catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      detail: "Broker-accumulation range is invalid",
    });
    expect((error as ApiError).message).toContain("HTTP 422");
    expect((error as ApiError).sanitizedBody).toContain("[REDACTED]");
    expect((error as ApiError).sanitizedBody).not.toContain("test-secret-value");
  });
});
