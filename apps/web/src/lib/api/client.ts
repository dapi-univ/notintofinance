import type {
  BrokerAccumulationResponse,
  DataStatus,
  HistoryResponse,
  StockListItem,
} from "./types";
import type { Timeframe } from "@/lib/chart/adapter";

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

export function fetchHistory(
  ticker: string,
  timeframe: Timeframe,
  signal?: AbortSignal,
): Promise<HistoryResponse> {
  const query = new URLSearchParams({ timeframe });
  return getJson(`/stocks/${encodeURIComponent(ticker)}/history?${query}`, signal);
}

export function fetchDataStatus(signal?: AbortSignal): Promise<DataStatus> {
  return getJson("/data/status", signal);
}

export function fetchBrokerAccumulation(
  ticker: string,
  dateFrom: string,
  dateTo: string,
  signal?: AbortSignal,
): Promise<BrokerAccumulationResponse> {
  const query = new URLSearchParams({ from: dateFrom, to: dateTo });
  return getJson(
    `/stocks/${encodeURIComponent(ticker)}/broker-accumulation?${query}`,
    signal,
  );
}
