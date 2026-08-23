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
- Historical contract: `startDate=endDate` is validated against the requested stored EOD
  session before any row is retained. A substituted date fails the ticker/session.
- Observed data quality: some normalized envelopes contain negative signed fields despite the
  documented non-negative examples. Those sessions are rejected and remain resumable; the
  adapter does not silently take absolute values or fabricate valid activity.

## Broker directory

- Path: `GET /brokers`
- Parameters: optional `type=LOCAL|FOREIGN`; operations use one unfiltered request.
- Data: `items[]` with canonical broker `code`, provider `name`, and provider classification;
  outer `count` must match the array length.
- Live bounded observation: 93 entries (66 LOCAL, 23 FOREIGN, 4 BUMN). BUMN is preserved as
  provider metadata rather than guessed into local/foreign.
- Provenance: gateway `zapi`, source provider `pluang`, source-observed timestamp, and ingestion
  timestamp are stored separately.

This is distinct from `finance:idx/broker-summary`, which is market-wide broker activity and
does not provide a stock ticker or BUY/SELL side. It is reserved as a separate future dataset
and is not substituted for per-stock flow.

## Running trades

- Path: `GET /running-trades`
- Parameters: `code`; optional `minLot`, `action=BUY|SELL`; continuation uses the opaque
  `cursor=<nextCursor>` unchanged.
- Data: `items[]`, `nextCursor`, `count`, `source`, and optional `stockId`.
- Item fields: `sequence`, Jakarta `time`, `price`, `lots`, and BUY/SELL `action`.
- Contract: executed prints without broker identity.
- Uniqueness: canonical stock, provider, session date and provider sequence.
- Cursor state: an active worker uses `running`; a page-capped exit retaining `nextCursor`
  uses `partial`. Only observed cursor exhaustion is `complete` for the declared filter.
- Collection floor: a requested IDR floor is translated with
  `ceil(min_trade_value_idr / (reference_price * 100))`. This is a storage/collection filter,
  not an analytical Big Money threshold.
- Session binding: the endpoint accepts no historical date and asserts no session date.
  Collection is allowed only for the latest PostgreSQL-confirmed EOD session with an EOD row
  for the ticker, and is blocked while a newer weekday session is unconfirmed.
- `high_water_mark` is the newest observed head; the opaque cursor continues toward older rows.
  Fetched counts are provider rows and retained counts are newly inserted canonical facts, so
  overlaps and retries do not inflate retention.

## Tradebook aggregates

- Path: `GET /tradebook`
- Parameters: canonical `code` and `tab=ALL|PRICE|TIME|VOLUME`.
- Data: normalized `byPrice`, `byTime`, and `byVolume` aggregate arrays, plus `items`.
- Observed price fields: `price`, buy/sell/pre/post/total frequency and lots.
- Observed time fields: `time`, buy lots and sell lots.
- Live bounded sample: `ALL` returned price and time views while `byVolume` was empty;
  a separate `VOLUME` request was also empty. Empty provider views are retained as absence,
  and a non-empty unvalidated volume shape is rejected instead of guessed.
- Contract: efficient daily structural aggregates. It can support price-level/directional
  research, but cannot replace running-trade sequencing or print-size distributions.
- Component availability is persisted independently. A successful empty `byVolume` is
  unavailable, not a synthesized zero-volume distribution. Tradebook uses the same
  `confirmed_latest_eod` fail-closed session binding as running trades.

## Orderbook

- Path: `GET /orderbook`
- Parameter: `code`.
- Data: normalized `bids[]` and `asks[]` containing `price` and `lots`, best prices and side
  counts/percentages.
- Observation time: the outer Zapi envelope timestamp.
- Contract: resting liquidity that may be cancelled; it is never labelled executed volume.

## Collection separation

Broker daily, tradebook, filtered running trades, and orderbook are independent operations.
The three-dataset canary remains available only for bounded comparisons. Orderbook stays
separately scheduled and is not approved for market-wide collection.

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
