"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchDataStatus, fetchHistory, fetchStocks } from "./client";
import type { Timeframe } from "@/lib/chart/adapter";

export function useStocks() {
  return useQuery({
    queryKey: ["stocks"],
    queryFn: ({ signal }) => fetchStocks(signal),
  });
}

export function useHistory(ticker: string, timeframe: Timeframe) {
  return useQuery({
    queryKey: ["history", ticker, timeframe],
    queryFn: ({ signal }) => fetchHistory(ticker, timeframe, signal),
    placeholderData: (previous) => previous,
  });
}

export function useDataStatus() {
  return useQuery({
    queryKey: ["data-status"],
    queryFn: ({ signal }) => fetchDataStatus(signal),
  });
}
