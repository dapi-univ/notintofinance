# OLT — IDX EOD Research Terminal

Dashboard V0 is a desktop-first Indonesian equities workspace with a thin navigation rail, searchable and resizable watchlist, mini sparklines, a synchronized candlestick/volume chart, and the Frequency Analyzer research pane.

Only Dashboard V0 is implemented. There is no landing page, authentication, billing, portfolio, screener, real-time stream, or future analytics module.

## Stack

- Next.js App Router, strict TypeScript, TanStack Query, Tailwind CSS, Lightweight Charts
- FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Supabase managed PostgreSQL through a server-side `DATABASE_URL`
- Zapi behind the `MarketDataProvider` protocol

## Local setup

Prerequisites: Node.js 24+, npm, and `uv`.

```bash
npm install
uv sync --project apps/api
```

Copy `.env.example` to `.env` and fill only the credentials available to the backend. Environment files are ignored by Git.

For credential-free local development, explicitly set `APP_ENV=development` and `MARKET_DATA_PROVIDER=mock`. The API uses deterministic in-memory fixtures and the UI displays `MOCK DATA` at all times. Selecting Zapi without `ZAPI_API_KEY` fails at startup; production and staging never fall back to mock data.

Start the services in separate terminals:

```bash
npm run dev:api
npm run dev:web
```

Open `http://localhost:3000/app`.

## Supabase PostgreSQL

The authoritative schema is [the Dashboard V0 migration](supabase/migrations/20260822154827_dashboard_v0.sql). It creates `stocks`, `daily_market_data`, and `ingestion_runs`, including validation constraints, idempotency keys, indexes, RLS, and browser-role revocations.

After connecting the Supabase CLI to the intended project:

```bash
npx supabase login
npx supabase link --project-ref <project-ref>
npx supabase db push
npx supabase migration list
```

Set `DATABASE_URL` to a server-side Supabase transaction-pooler URL for the API. Never prefix database credentials or a service-role key with `NEXT_PUBLIC_`.

Alembic is available for non-Supabase deployment workflows and executes the same authoritative SQL file:

```bash
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

Use one migration history mechanism per environment; managed Supabase deployments should use the Supabase CLI.

## Zapi ingestion

Zapi uses the documented `finance:idx/stock-history` and `stock-summary` endpoints. Configure:

```dotenv
DATABASE_URL=postgresql://...
MARKET_DATA_PROVIDER=zapi
ZAPI_API_KEY=zpi_...
ZAPI_BASE_URL=https://api.zpi.web.id/v1/finance:idx
```

Then ingest one or more symbols:

```bash
uv run --project apps/api python -m app.cli BBCA ANTM TLKM --from 2025-01-01 --to 2026-08-21
```

Ingestion validates source data and atomically upserts `(stock_id, trade_date)`. Volume remains in shares. Lots are derived as shares divided by 100.

## Frequency Analyzer

The research formula is:

```text
FA_raw = Volume / Frequency^3
```

The API returns distinct share-based and lot-based raw values. Frequency zero returns `null`; impossible negative inputs fail validation. The chart registry applies a named `log10(raw shares)` visualization transform without changing raw values.

## Verification

```bash
npm run lint
npm run typecheck
npm run test
npm run build --workspace @idx-terminal/web
npx playwright install chromium
npm run test:e2e
```

The frontend suite executes the PostgreSQL migration in PGlite and checks its uniqueness contract. Backend tests cover formula examples, invalid OHLC rejection, Zapi mapping, duplicate ingestion, freshness, and the API data flow. Playwright covers the complete `/app` workspace flow.

## API

- `GET /health`
- `GET /stocks`
- `GET /stocks/{ticker}`
- `GET /stocks/{ticker}/history`
- `GET /data/status`

The frontend never contacts Zapi or Supabase directly.
