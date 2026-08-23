# Zapi EOD Data Inventory

Verified against the public Zapi scraper catalog and authenticated live responses on
2026-08-23. Examples and credentials are intentionally omitted.

## Authentication and transport

- Base scraper: `finance:idx`
- Authentication: `x-api-key` request header
- Live response envelope: `{ "project": ..., "data": ..., "timestamp": ... }`
- The adapter also accepts the legacy direct dataset body for `stock-history`.
- Request timeout: 30 seconds.
- Retryable failures: network errors, HTTP 429, and HTTP 5xx responses. The client uses
  bounded exponential backoff with jitter and honors `Retry-After` when supplied.
- Live headers on 2026-08-23 reported 2,000 requests remaining per minute and 24,452
  remaining for the month before Phase 1 ingestion. `X-RateLimit-Limit` and
  `X-Plan-Expired` were absent. Missing headers are persisted as warnings and never treated
  as unlimited quota. Quotas are plan-specific and are re-checked before a large backfill.

## IDX securities universe

- Endpoint: `GET /v1/finance:idx/securities`
- Dataset/grain: one row per listed IDX security.
- Parameters:
  - `start`: zero-based offset, default 0.
  - `length`: page size, 1 through 1000, default 20.
  - `code`, `sector`, `board`: optional provider filters.
- Dataset body:
  - `data`: security rows.
  - `start`, `length`, `recordsTotal`, `recordsFiltered`.
  - `dataset="securities"`, `provider="idx"` when present.
- Canonical mapping:
  - `Code` -> `stocks.ticker` (uppercase).
  - `Name` -> `stocks.company_name`.
  - `ListingDate`, `Shares`, and `ListingBoard` are observed but are not stored in the
    current Dashboard V0 schema.
- Units: `Shares` is the number of listed shares. It is not daily traded volume.
- Pagination: maximum page size is 1000. A complete synchronization continues until the
  unique ticker count equals `recordsFiltered`; incomplete pagination is rejected.
- Update cadence/cache: listing metadata changes irregularly; catalog cache TTL is 21,600
  seconds (six hours).
- Live observation: 962 rows were reported on 2026-08-23.
- Missing/ambiguous fields:
  - The response has no explicit active/delisted flag. KEJORA treats membership in a
    successfully fetched complete `securities` result as active.
  - Sector and subsector are not present in observed rows, so they remain null rather than
    being inferred.
  - If `Name` is blank, the ticker itself is used as an explicit fallback label to satisfy
    the existing nonblank database constraint; no company name is invented.

## Stock EOD history

- Endpoint: `GET /v1/finance:idx/stock-history`
- Dataset/grain: one row per ticker and trading date.
- Required parameter: `code`.
- Range parameters:
  - `length`: 1 through 2000 trading sessions; default 30 when `from` is absent.
  - `from`, `to`: `YYYY-MM-DD` or `YYYYMMDD`; when `from` is supplied the provider derives
    the returned length from the date range.
- Dataset body:
  - `code`, `name`, `from`, `to`, `count`, `items`.
  - `dataset="stock-history"`, `provider="idx"`, `unit="shares"`, and
    `valueBasis="close"` were observed live.
- Canonical item mapping:
  - `date` -> `trade_date`.
  - `open`, `high`, `low`, `close`, `previous` -> IDR price fields.
  - `volume` -> `volume_shares`.
  - `value` -> `value_idr`.
  - `frequency` -> trade frequency count.
  - `foreignBuyShares`, `foreignSellShares` -> daily foreign share flows.
  - `netForeignShares` is provider-supplied but KEJORA derives its public value as
    `foreign_buy_shares - foreign_sell_shares` from stored canonical columns.
- Units:
  - `unit`, when present, must equal exactly `shares`; any other value is rejected.
  - Missing `unit` remains supported for legacy direct responses.
  - Price/value are observed as IDR fields; daily volume and foreign flows are raw shares.
  - `frequency` is a count.
- Retention/practical range: the catalog documents history available back to 2020 and a
  maximum of 2000 trading sessions per request. Operational V1 targets the latest 260
  sessions per active ticker and re-fetches a small recent date window for revisions.
- Update cadence/cache: EOD trading data; catalog cache TTL is 60 seconds.
- Missing/ambiguous fields:
  - Exchange holidays and final market-close availability are not described by the
    endpoint schema.
  - Foreign monetary fields are present in observed payloads, but Operational V1 does not
    expose them because the requested canonical feature is share-based foreign flow.
  - No broker identity or proprietary influence score is provided.
  - Some suspended/non-trading sessions can contain zero OHLC values. The validated
    adapter rejects those individual rows, records the rejected count, and retains valid
    rows for the ticker rather than storing invalid OHLC data.

## Operational notes

- Normal application reads are PostgreSQL-only. Zapi is invoked only by the ingestion CLI.
- `daily_market_data` is upserted on `(stock_id, trade_date)` and never replaced wholesale.
- Provider failure leaves previously stored history readable.
- Phase 1 enforces a 2,500-request monthly reserve, an 800-request default daily soft budget,
  and explicit run caps. Checkpoint-based resume remains mandatory even when the observed
  allowance can cover the current universe.
