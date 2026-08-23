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
- Market-wide EOD snapshots keep non-regular activity separate and retain provider-observed
  listed/tradeable share and index metadata. Index-related fields are not labelled official
  portfolio weights without independent semantic confirmation.
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
- `broker_directory` is the provider-neutral master used to enrich broker-flow reads. It retains
  provider names/classifications and separate Zapi-gateway/Pluang-source timestamps.
- `tradebook_aggregates` stores the provider's daily price/time aggregate buckets. Missing
  views remain missing; no bucket is synthesized.
- `tradebook_collection_sessions` records PRICE/TIME/VOLUME availability and the fail-closed
  EOD session binding even when a component is empty.
- `trade_prints` stores executed prints uniquely by stock, provider, session and provider
  sequence. One lot is converted deterministically to 100 shares. No broker field exists.
  Gateway observation time, binding method and the provider-date assertion flag stay separate;
  the current provider does not assert a session date.
- `orderbook_snapshots` and `orderbook_levels` separate observed snapshot metadata from
  resting bid/ask liquidity. They are not executed volume.
- `data_quality_events` classifies retryability and terminal failures with sanitized context.
- `ingestion_cursors` persists cursor/high-water progress for resumable cursor datasets.
  It is scoped by provider/dataset/instrument/session and retains collection filter/floor and
  fetched/retained counts. `running` means an active worker, `partial` retains a continuation,
  and only observed exhaustion is `complete`.

All Phase 1 tables use bigint identity primary keys, indexed foreign keys, typed numeric/time
columns, RLS without browser policies, and revoked `anon`/`authenticated` privileges.
