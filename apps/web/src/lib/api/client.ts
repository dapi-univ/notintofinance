import type { DataStatus, HistoryResponse, StockListItem } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const message = response.status === 404 ? "Market data was not found." : "Market data is unavailable.";
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function fetchStocks(signal?: AbortSignal): Promise<StockListItem[]> {
  return getJson("/stocks", signal);
}

export function fetchHistory(ticker: string, signal?: AbortSignal): Promise<HistoryResponse> {
  return getJson(`/stocks/${encodeURIComponent(ticker)}/history?limit=520`, signal);
}

export function fetchDataStatus(signal?: AbortSignal): Promise<DataStatus> {
  return getJson("/data/status", signal);
}
