# Zapi finance:pluang Market Data Inventory

Verified against Zapi's documented `finance:pluang` reference and authenticated normalized
responses on 2026-08-23. Production requests use only:

`https://api.zpi.web.id/v1/finance:pluang`

with the server-side `x-api-key`. The normalized data source remains `pluang`; the API gateway
and quota owner are `zapi`. No browser impersonation headers or direct-upstream fallback are
used. Keys, authenticated URLs and production payload values are omitted from this document.

Live responses use a Zapi envelope:

`{"data": {...}, "project": "...", "timestamp": "..."}`

The nested normalized object must carry `source="pluang"` and the requested canonical IDX
ticker. Both `finance:idx` and `finance:pluang` consume the same persisted Zapi quota budget.

## Instrument resolution

- Path: `GET /resolve`
- Parameters: `code` (required canonical IDX ticker).
- Data: `code`, `source`, `stockId`.
- Use: optional cached metadata or a small validation canary only. Broker, trade and orderbook
  endpoints accept `code` directly, so a 962-ticker resolve pass is not required.

## Per-stock broker summary

- Path: `GET /broker-summary`
- Parameters: `code`, `startDate`, `endDate`, `net=true`.
- Data: `buyers[]`, `sellers[]`, `capped`, `count`, range, source and optional `stockId`.
- Row fields: canonical IDX broker `broker`, `lots`, IDR `value`, and `averagePrice`.
- Coverage: `capped=true` is persisted as `source_scope='top_n'` with the documented count in
  `source_top_n`; it is never represented as complete-market broker flow.
- Units: one lot is converted deterministically to 100 shares.

This is distinct from `finance:idx/broker-summary`, which is market-wide broker activity and
does not provide a stock ticker or BUY/SELL side. It is reserved as a separate future dataset
and is not substituted for per-stock flow.

## Running trades

- Path: `GET /running-trades`
- Parameters: `code`; continuation uses `cursor=<opaque nextCursor>`.
- Data: `items[]`, `nextCursor`, `count`, `source`, and optional `stockId`.
- Item fields: `sequence`, Jakarta `time`, `price`, `lots`, and BUY/SELL `action`.
- Contract: executed prints without broker identity.
- Uniqueness: canonical stock, provider, session date and provider sequence.
- Cursor state: an active worker uses `running`; a page-capped exit retaining `nextCursor`
  uses `partial`.

## Orderbook

- Path: `GET /orderbook`
- Parameter: `code`.
- Data: normalized `bids[]` and `asks[]` containing `price` and `lots`, best prices and side
  counts/percentages.
- Observation time: the outer Zapi envelope timestamp.
- Contract: resting liquidity that may be cancelled; it is never labelled executed volume.

## Reserved later endpoint

`GET /tradebook` is documented but intentionally not ingested in Phase 1.1. It is reserved for
the later Frequency Analyzer research phase after audit approval.

## Quota and retry contract

- Request ledger gateway: `zapi`.
- Endpoint names: `finance:pluang/<endpoint>`.
- Parse and persist Zapi limit, minute remaining, month remaining and plan-expired headers.
- Missing or malformed quota headers remain explicit warnings, never unlimited capacity.
- The first request initializes monthly remaining from the latest persisted Zapi ledger row.
- Network failures, HTTP 429 and 5xx use bounded retry; `Retry-After` is honored exactly.
- Ordinary 4xx responses are not blindly retried.
- A 2,500-request monthly reserve, daily soft budget and strict canary cap remain enforced.

Raw staging stores the complete normalized Zapi envelope with `gateway='zapi'` and
`source_provider='pluang'`. Existing historical direct-source records and ledger events are
retained unchanged.
