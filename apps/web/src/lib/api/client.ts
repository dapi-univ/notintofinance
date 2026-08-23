import type {
  BrokerAccumulationResponse,
  DataStatus,
  HistoryResponse,
  StockListItem,
} from "./types";
import type { Timeframe } from "@/lib/chart/adapter";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MAX_DIAGNOSTIC_BODY_LENGTH = 2_000;
const SENSITIVE_FIELD = /api[-_]?key|authorization|cookie|password|secret|token/i;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: string | null,
    readonly sanitizedBody: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function sanitizeText(value: string): string {
  return value
    .replace(/(bearer\s+)[a-z0-9._~-]+/gi, "$1[REDACTED]")
    .replace(
      /((?:api[-_]?key|password|secret|token)\s*(?:=|:)\s*)[^\s,;"'}]+/gi,
      "$1[REDACTED]",
    )
    .replace(/([a-z][a-z0-9+.-]*:\/\/[^:/\s]+:)[^@\s]+@/gi, "$1[REDACTED]@");
}

function sanitizeValue(value: unknown, field?: string): unknown {
  if (field && SENSITIVE_FIELD.test(field)) return "[REDACTED]";
  if (typeof value === "string") return sanitizeText(value);
  if (Array.isArray(value)) return value.map((item) => sanitizeValue(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeValue(item, key)]),
    );
  }
  return value;
}

async function responseError(response: Response): Promise<ApiError> {
  const rawBody = await response.text().catch(() => "");
  let parsedBody: unknown = rawBody;
  if (rawBody) {
    try {
      parsedBody = JSON.parse(rawBody) as unknown;
    } catch {
      // Non-JSON responses are retained below as bounded sanitized text.
    }
  }
  const sanitized = sanitizeValue(parsedBody);
  const sanitizedBody = (
    typeof sanitized === "string" ? sanitized : JSON.stringify(sanitized)
  ).slice(0, MAX_DIAGNOSTIC_BODY_LENGTH);
  const detailValue =
    sanitized && typeof sanitized === "object" && !Array.isArray(sanitized)
      ? (sanitized as Record<string, unknown>).detail
      : null;
  const detail =
    typeof detailValue === "string"
      ? detailValue
      : detailValue == null
        ? null
        : JSON.stringify(detailValue);
  const fallback =
    response.status === 404 ? "Market data was not found." : "Market data is unavailable.";
  return new ApiError(
    `HTTP ${response.status}: ${detail || fallback}`,
    response.status,
    detail,
    sanitizedBody,
  );
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response);
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
