"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchBrokerAccumulation,
  fetchDataStatus,
  fetchHistory,
  fetchStocks,
} from "./client";
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

export function useBrokerAccumulation(
  ticker: string,
  dateFrom: string | undefined,
  dateTo: string | undefined,
  enabled: boolean,
) {
  const queryClient = useQueryClient();
  const queryKey = ["broker-accumulation", ticker, dateFrom, dateTo] as const;
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      fetchBrokerAccumulation(ticker, dateFrom ?? "", dateTo ?? "", signal),
    enabled: enabled && Boolean(dateFrom && dateTo),
  });
  return {
    ...query,
    retry: () => queryClient.resetQueries({ queryKey, exact: true }),
  };
}
