# OLT — IDX EOD Research Terminal

KEJORA is a desktop-first Indonesian equities workspace with a thin navigation rail,
searchable and resizable database-backed stock universe, mini sparklines, synchronized
price/volume charts, Frequency Analyzer, and share-based Foreign Analysis.

The EOD operational slice is implemented. There is no landing page, authentication,
billing, portfolio, screener, real-time stream, broker analytics, or intraday collector.

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

The authoritative schema is the ordered SQL history in `supabase/migrations`. It creates
`stocks`, `daily_market_data`, `ingestion_runs`, and private resumable
`ingestion_checkpoints`, including validation constraints, idempotency keys, indexes, RLS,
and browser-role revocations.

After connecting the Supabase CLI to the intended project:

```bash
npx supabase login
npx supabase link --project-ref <project-ref>
npx supabase db push
npx supabase migration list
```

Set `DATABASE_URL` to a server-side Supabase pooler URL for the API. Never prefix database
credentials or a service-role key with `NEXT_PUBLIC_`.

Alembic is available for non-Supabase deployment workflows and executes the same authoritative SQL file:

```bash
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

Use one migration history mechanism per environment; managed Supabase deployments should use the Supabase CLI.

## Zapi ingestion

Zapi uses the verified `finance:idx/securities` and `finance:idx/stock-history` endpoints.
See [the sanitized data inventory](docs/ZAPI_EOD_DATA_INVENTORY.md). Configure:

```dotenv
DATABASE_URL=postgresql://...
MARKET_DATA_PROVIDER=zapi
ZAPI_API_KEY=zpi_...
ZAPI_BASE_URL=https://api.zpi.web.id/v1/finance:idx
```

Discover without writing, synchronize the universe, or run selected symbols:

```bash
uv run --project apps/api python -m app.cli --discover-only
uv run --project apps/api python -m app.cli --sync-universe-only
uv run --project apps/api python -m app.cli BBCA ANTM TLKM --mode auto --concurrency 2
```

Initial backfill and incremental refresh are also explicit:

```bash
uv run --project apps/api python -m app.cli BBRI BMRI --mode backfill --sessions 260
uv run --project apps/api python -m app.cli --all-active --mode auto --concurrency 2
```

Resume only failed checkpoints without spending another universe request:

```bash
uv run --project apps/api python -m app.cli --resume --mode auto --concurrency 2 --skip-universe-sync
```

Ingestion validates source data, isolates ticker failures, and atomically upserts
`(stock_id, trade_date)`. A successful second execution is idempotent; complete histories
only re-fetch a 14-day revision window. Volume remains in shares. Lots are derived as shares
divided by 100.

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

The frontend suite executes the PostgreSQL migration in PGlite and checks its uniqueness
contract. Backend tests cover formula examples, invalid OHLC filtering, both Zapi envelopes,
universe synchronization, resumable ingestion, foreign calculations, freshness, and API
data flow. Playwright covers ticker discovery and all operational EOD panes.

## API

- `GET /health`
- `GET /stocks?q={ticker-or-company}&limit={1..1000}`
- `GET /stocks/{ticker}`
- `GET /stocks/{ticker}/history`
- `GET /data/status`

The frontend never contacts Zapi or Supabase directly.
