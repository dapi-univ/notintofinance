# Dashboard V0 Architecture

Dashboard V0 is a two-application monorepo:

- `apps/web`: Next.js App Router workspace. It talks only to FastAPI.
- `apps/api`: FastAPI service, provider adapters, validation, analytics, and PostgreSQL persistence.
- `supabase/migrations`: authoritative managed-PostgreSQL schema.

The production data path is:

`Zapi -> MarketDataProvider -> Pydantic validation -> repository upsert -> Supabase PostgreSQL -> FastAPI -> TanStack Query -> Lightweight Charts`

Phase 1 adds a provider-neutral operational path alongside the stable dashboard path:

`Zapi finance:idx / finance:pluang -> quota-aware transport -> sanitized raw staging -> typed normalization -> warehouse repositories -> Supabase PostgreSQL -> FastAPI`

Provider instrument identifiers are optional mappings only; `stocks.id` and the IDX ticker
remain canonical. Pluang-source broker-flow, running-trade and orderbook data is requested
only through Zapi's documented `finance:pluang` namespace with the server-side Zapi key.
There is no direct-upstream fallback or browser-header impersonation. Orderbook rows are
resting-liquidity snapshots, running trades are executed prints without broker identity, and
broker summaries explicitly retain their capped top-10 scope.

When `DATABASE_URL` or `ZAPI_API_KEY` is unavailable, development starts with the explicit `mock` provider and an in-memory repository. Mock responses include `is_mock: true`, and the web workspace shows a persistent `MOCK DATA` badge. Mock mode is never presented as live market data.

## State boundaries

- Server state: stocks, history, sparklines, ingestion status, freshness.
- Client UI state: ticker, timeframe, watchlist width/collapse, indicator visibility.
- The selected ticker is persisted in the `/app?ticker=...` URL.

## EOD operations

The `securities` dataset synchronizes the active stock universe. Per-ticker history uses a
bounded worker pool, recent-window refreshes, idempotent database upserts, and private
checkpoints. One ticker failure is recorded without rolling back other completed symbols.
Normal API reads do not instantiate or call the provider.

Ordinary EOD collection uses one market-wide `stock-summary` response with independent row
validation and upserts. `stock-history` remains the per-ticker backfill, reconciliation, and
targeted-repair path. Broker daily, tradebook, filtered running trades, and orderbook are
separate operations with their own cadence and quota economics.

Every gateway attempt is fingerprinted without credentials and recorded with latency,
status, attempt number, row count, cache status, and available quota headers. Both
`finance:idx` and `finance:pluang` consume one shared Zapi budget initialized from the latest
persisted monthly-remaining observation. Zapi ingestion stops non-critical work at the
configured daily soft budget or 2,500-request monthly reserve.
Canaries have a separate hard request cap. Advisory locks prevent concurrent ingestion of
the same dataset session.

## Analytics

Raw values are calculated in the API as `volume / frequency^3`. Share and lot research series are returned separately. The frontend registry applies an explicitly named `log10(raw shares)` visualization transform without overwriting either raw series.

Foreign buy and sell shares are stored as supplied. Daily net shares and cumulative net
shares for the selected chart range are derived in the API and rendered by the existing
registry-driven chart lifecycle.

## Database access

FastAPI uses a pooled server-side PostgreSQL connection. The browser never receives database
credentials. Public-schema tables, including `alembic_version`, have RLS enabled and browser
roles have no grants; the application does not use Supabase Auth, Storage, Realtime, or Edge
Functions.

Raw provider payloads are sanitized, backend-only, hash-deduplicated, and assigned a bounded
expiry. Gateway and normalized source provenance are stored separately. They are never
returned from API routes.
