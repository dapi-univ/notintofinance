"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchDataStatus, fetchHistory, fetchStocks } from "./client";

export function useStocks() {
  return useQuery({
    queryKey: ["stocks"],
    queryFn: ({ signal }) => fetchStocks(signal),
  });
}

export function useHistory(ticker: string) {
  return useQuery({
    queryKey: ["history", ticker],
    queryFn: ({ signal }) => fetchHistory(ticker, signal),
    placeholderData: (previous) => previous,
  });
}

export function useDataStatus() {
  return useQuery({
    queryKey: ["data-status"],
    queryFn: ({ signal }) => fetchDataStatus(signal),
  });
}
