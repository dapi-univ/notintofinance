# Pluang Market Data Inventory

Verified against the official Pluang web application and live responses on 2026-08-23.
Credentials, sensitive headers, full URLs, and raw production payloads are intentionally
omitted. The public web client uses a wrapped response envelope:

`{"data": ..., "statusCode": 200, "timestamp": "..."}`

The collector validates `statusCode`, object envelopes, numeric fields, timestamps and units
before persistence. Phase 1 uses at most three symbols, three cursor pages per symbol and one
orderbook snapshot per symbol for microstructure collection.

## Instrument mapping

- Sanitized path: `GET /api/v2/indo-stock/description-by-code`
- Parameter: `stockCode` (canonical IDX ticker)
- Response data: `{ "id": <positive integer> }`
- Canonical mapping: `data.id` -> provider instrument ID; the ticker and internal
  `stocks.id` remain canonical KEJORA identities.
- Observed canary mappings: AADI, BBCA and TLKM resolved uniquely.

## Broker summary

- Sanitized path: `GET /api/v2/indo-stock/broker/summary`
- Parameters: `stockId`, `startDate`, `endDate`, `net`
- Response data: `startDate`, `endDate`, `net`, `brokerSummary[]`
- Each ranked row pairs buyer and seller code, lot volume, IDR value and average price.
- Coverage: top buyers/sellers, normally top 10. KEJORA persists
  `source_scope='top_n'` and `source_top_n=10`; it never represents this as complete broker
  coverage.
- Units: lots, IDR and IDR/share average price. Shares are derived as `lots * 100`.

## Running trades

- Sanitized path: `GET /api/v2/indo-stock/market-feed/running-trades`
- Parameters: `stockId`; subsequent pages use `next=<opaque cursor>`.
- Response data: `rt[]` and `next`.
- Print fields: `seq`, `time`, `price`, `lot`, and `action` (`BUY`/`SELL`).
- Contract: executed prints; no broker identity is present or inferred.
- The stored session date is the latest confirmed PostgreSQL market date, and time-of-day is
  interpreted in `Asia/Jakarta` before storing a timezone-aware timestamp.
- Uniqueness: canonical stock, provider, session date and provider sequence.
- A page cap with a non-empty `next` token is stored as resumable partial progress, not a
  completed cursor. The next canary run for the same session continues from that token.

## Orderbook

- Sanitized path: `GET /api/v2/indo-stock/market-feed/orderbook`
- Parameter: `stockId`
- Response data: `bids[]`, `asks[]`, subscription metadata and side percentages.
- Level fields: `p` (price) and `l` (lots). Best bid/ask and spread are derived from validated
  levels.
- Contract: resting liquidity observed at the response timestamp. Levels may be cancelled
  and are never labelled as executed volume.

## Operational observations

- The official client sends no cookie, authorization bearer or API key for these market-data
  reads; it supplies ordinary browser content-negotiation, language, request-ID and referrer
  headers.
- Pluang did not return Zapi-style quota headers. This is recorded as an undocumented quota,
  not interpreted as unlimited capacity. KEJORA therefore enforces its own daily and canary
  caps.
- A live three-symbol canary used three pages per running-trades cursor, one broker request
  and one orderbook request per symbol. No mass intraday collection is part of Phase 1.
