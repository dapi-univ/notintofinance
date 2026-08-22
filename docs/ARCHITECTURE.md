# Dashboard V0 Architecture

Dashboard V0 is a two-application monorepo:

- `apps/web`: Next.js App Router workspace. It talks only to FastAPI.
- `apps/api`: FastAPI service, provider adapters, validation, analytics, and PostgreSQL persistence.
- `supabase/migrations`: authoritative managed-PostgreSQL schema.

The production data path is:

`Zapi -> MarketDataProvider -> Pydantic validation -> repository upsert -> Supabase PostgreSQL -> FastAPI -> TanStack Query -> Lightweight Charts`

When `DATABASE_URL` or `ZAPI_API_KEY` is unavailable, development starts with the explicit `mock` provider and an in-memory repository. Mock responses include `is_mock: true`, and the web workspace shows a persistent `MOCK DATA` badge. Mock mode is never presented as live market data.

## State boundaries

- Server state: stocks, history, sparklines, ingestion status, freshness.
- Client UI state: ticker, timeframe, watchlist width/collapse, indicator visibility.
- The selected ticker is persisted in the `/app?ticker=...` URL.

## Frequency Analyzer

Raw values are calculated in the API as `volume / frequency^3`. Share and lot research series are returned separately. The frontend registry applies an explicitly named `log10(raw shares)` visualization transform without overwriting either raw series.

## Database access

FastAPI uses a pooled server-side PostgreSQL connection. The browser never receives database credentials. Public-schema tables have RLS enabled and browser roles have no grants; V0 does not use Supabase Auth, Storage, Realtime, or Edge Functions.
