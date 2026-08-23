# Dashboard V0 Data Model

The authoritative schema is the SQL migration under `supabase/migrations`.

- Prices and IDR values use exact `numeric` values.
- Volume and frequency use `bigint` source units.
- `volume_shares` always stores shares; lots are derived as `volume_shares / 100`.
- `daily_market_data` is unique on `(stock_id, trade_date)` for idempotent ingestion.
- `ingestion_runs` records provider, requested date, row counts, status, and any sanitized failure message.
- `ingestion_checkpoints` records provider/dataset/ticker progress, the latest successful
  market date and fetch time, status, and a bounded diagnostic.
- Foreign buy and sell values are stored as raw shares. Daily and range-cumulative net
  values are derived at read time and are not persisted as competing source truth.
- All timestamps use `timestamptz`.
- Every public table has RLS enabled, no browser policy, and no `anon` or `authenticated`
  table privileges.

## Shared Market Warehouse Phase 1

- `instrument_provider_mappings` relates canonical stocks to provider identifiers without
  replacing `stocks.id`; mapping outcomes are mapped, unsupported, ambiguous, or transient.
- `provider_request_ledger` stores sanitized request fingerprints, attempts, latency, status,
  cache and quota observations. It never stores authenticated URLs or headers.
- `raw_provider_payloads` is bounded, hash-deduplicated staging with explicit gateway,
  normalized source, normalization status and expiry.
- `broker_flow_daily` stores one typed buy/sell row per ranked broker and date range. Pluang
  rows have `source_scope='top_n'` and `source_top_n=10`; they are not complete-market flow.
- `trade_prints` stores executed prints uniquely by stock, provider, session and provider
  sequence. One lot is converted deterministically to 100 shares. No broker field exists.
- `orderbook_snapshots` and `orderbook_levels` separate observed snapshot metadata from
  resting bid/ask liquidity. They are not executed volume.
- `data_quality_events` classifies retryability and terminal failures with sanitized context.
- `ingestion_cursors` persists cursor/high-water progress for resumable cursor datasets.
  `running` means an active worker; a capped run retaining `nextCursor` is `partial`.

All Phase 1 tables use bigint identity primary keys, indexed foreign keys, typed numeric/time
columns, RLS without browser policies, and revoked `anon`/`authenticated` privileges.
