---
name: idx-terminal-dashboard
description: Build and refine a high-density Indonesian stock analytics terminal. Optimized for Next.js trading dashboards with collapsible navigation, watchlists, fast symbol switching, Lightweight Charts, modular indicator panes, Supabase Postgres, strict performance budgets, and production-grade interaction states. Use for the /app trading workspace, not for marketing landing pages.
---

# IDX Terminal Dashboard Skill

## 0. Mission

Build a professional Indonesian stock analytics workspace centered around a single charting terminal.

This is NOT a landing page, generic admin panel, KPI-card dashboard, or decorative fintech concept.

Primary mental model:

- Stockbit-like workspace efficiency:
  - thin icon navigation rail
  - watchlist panel
  - mini sparklines
  - large central chart
  - fast symbol switching
- Bandar-Metrics-like analytics workflow:
  - proprietary analytics exposed from an Indicators menu inside the chart workspace
  - indicators render as overlays or synchronized panes
- Independent visual system:
  - do not copy branding, logos, exact spacing, colors, labels, or proprietary UI assets
  - reproduce only useful interaction patterns

The dashboard must feel like a research terminal used nightly after IDX close.

## 1. Product Read

Before changing code, output one line:

"Dashboard Read: dense EOD Indonesian equities research terminal, desktop-first, chart-centric, low-motion, high information density."

Unless explicitly overridden, lock these values:

- DESIGN_VARIANCE: 3/10
- MOTION_INTENSITY: 2/10
- VISUAL_DENSITY: 9/10

These values override generic marketing-page defaults.

## 2. Hard Scope for V0

V0 must contain only:

1. Application shell
2. Thin left navigation rail
3. Collapsible/resizable watchlist panel
4. Watchlist search
5. Watchlist rows with ticker, company name, last price, daily change, mini sparkline
6. Main chart workspace
7. Symbol header
8. Timeframe controls
9. Indicators menu
10. Candlestick price chart
11. Volume pane
12. Frequency Analyzer pane
13. Loading, empty, stale-data, and error states
14. Supabase-backed historical EOD data
15. Data freshness/status indicator

Do NOT build yet:

- landing page
- authentication
- billing
- portfolio
- social feed
- AI analyst
- alerts
- screener implementation
- broker analysis
- big matched transaction engine
- foreign scoring engine
- mobile-native trading UX
- real-time streaming
- WebSockets
- Redis
- Kafka
- Celery

Navigation items for future modules may be disabled only if useful for spatial planning. Prefer hiding unfinished features.

## 3. Stack Lock

Frontend:
- Next.js App Router
- TypeScript strict mode
- React Server Components by default
- Client Components only where interaction requires them
- Tailwind CSS
- shadcn/ui only for primitives that benefit from it; customize them
- TanStack Query for server-state fetching/caching
- Zustand only if cross-workspace client state becomes painful through props
- TradingView Lightweight Charts for primary financial charts
- TanStack Table later for screeners/tables
- one icon family only

Backend:
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- Python type hints

Data:
- Supabase Postgres as managed PostgreSQL
- Zapi provider initially
- provider abstraction mandatory

Testing:
- Vitest or Jest for frontend units
- Playwright for critical workspace flows
- Pytest for backend
- Ruff for Python linting
- mypy or pyright for Python type checks if practical
- ESLint + TypeScript check for frontend

## 4. Repository Contract

Preferred structure:

```text
/
├─ apps/
│  ├─ web/
│  └─ api/
├─ skills/
│  └─ idx-terminal-dashboard/
│     └─ SKILL.md
├─ docs/
│  ├─ DASHBOARD_V0_SPEC.md
│  ├─ DATA_MODEL.md
│  └─ ARCHITECTURE.md
├─ AGENTS.md
├─ .env.example
└─ README.md
```

Frontend suggested structure:

```text
apps/web/
├─ app/
│  └─ app/
│     ├─ page.tsx
│     └─ stocks/[ticker]/page.tsx
├─ components/
│  ├─ shell/
│  ├─ watchlist/
│  ├─ chart/
│  ├─ indicators/
│  └─ states/
├─ lib/
│  ├─ api/
│  ├─ chart/
│  ├─ format/
│  └─ types/
└─ stores/
```

Backend suggested structure:

```text
apps/api/app/
├─ api/
├─ core/
├─ db/
├─ models/
├─ schemas/
├─ repositories/
├─ providers/
├─ analytics/
└─ services/
```

Do not put market calculations in React components or API route handlers.

## 5. Workspace Layout Contract

Desktop layout:

```text
┌──────┬──────────────────────┬──────────────────────────────────────────┐
│ NAV  │ WATCHLIST            │ CHART WORKSPACE                          │
│ RAIL │                      │                                          │
│      │ Search               │ Symbol header                            │
│      │                      │ Toolbar                                  │
│ WL   │ ANTM  +0.96%         │                                          │
│ SC   │  sparkline           │ Candlestick                              │
│ DATA │                      │                                          │
│ SET  │ BBCA  +0.78%         ├──────────────────────────────────────────┤
│      │  sparkline           │ Volume                                   │
│      │                      ├──────────────────────────────────────────┤
│      │ ...                  │ Frequency Analyzer                       │
└──────┴──────────────────────┴──────────────────────────────────────────┘
```

Rules:

- Chart workspace receives the majority of horizontal space.
- Navigation rail is narrow and icon-first.
- Watchlist width is bounded and resizable.
- Watchlist can collapse to preserve chart area.
- Do not surround every region with rounded cards.
- Prefer 1px dividers and layered surfaces.
- Avoid giant top headers.
- Avoid marketing hero typography.
- Numbers should be tabular and easy to scan.
- Price, percent, volume, frequency and indicator values must align predictably.

## 6. Responsive Strategy

This product is desktop-first.

Breakpoints:

- >= 1280px: full rail + watchlist + chart
- 1024-1279px: narrower watchlist
- 768-1023px: collapsible watchlist drawer, chart primary
- < 768px: functional read-only compact chart view; do not attempt to recreate full desktop terminal density

The desktop terminal is the priority. Mobile must not break, but V0 does not need full feature parity.

## 7. Visual System

Theme:
- dark-first financial workstation
- light mode optional later
- use semantic CSS variables/tokens
- no pure black
- no neon glow
- no purple AI-gradient default
- max one primary accent color
- green/red only for semantic market direction where needed
- keep neutral surfaces distinguishable with subtle luminance steps

Typography:
- neutral sans UI font
- tabular numerals
- monospace only where it improves scanning of market numbers
- no serif in dashboard
- no oversized headings

Shape:
- compact radius system
- use cards only when they communicate hierarchy
- toolbars, lists, panes and chart regions should mostly use dividers

Motion:
- state feedback only
- panel collapse/expand
- menu open/close
- selected ticker transition
- no decorative looping animation
- no parallax
- no scroll storytelling

## 8. Core Interaction Rules

### Navigation Rail
- icon-only default
- tooltip on hover/focus
- active item visible without glow
- keyboard reachable

### Watchlist
Each row should support:
- ticker
- company name
- latest close
- daily absolute change
- daily percent change
- compact sparkline

Behavior:
- clicking a ticker changes the active symbol without full page reload
- selected symbol is reflected in the URL where practical
- keyboard arrows may be added only after click behavior is solid
- list scrolling must not block page/chart behavior
- collapsing the watchlist preserves selected symbol

### Chart
- chart must resize correctly when watchlist collapses or window changes
- price and all indicator panes share the same time scale
- crosshair synchronization across panes
- no pane should drift in time alignment
- chart state must survive simple UI interactions when practical

### Indicators Menu
V0 entries:
- Volume
- Frequency Analyzer

Future registry placeholders:
- Foreign Flow
- Foreign Influence
- NFB/NFS
- Big Matched Transactions

Do not expose unfinished future indicators as working.

## 9. Indicator Plugin Contract

Indicators must be registry-driven.

Concept:

```ts
type IndicatorDefinition = {
  id: string
  label: string
  kind: "overlay" | "pane"
  defaultVisible: boolean
  requires: string[]
  createSeries: (...)
  transform: (...)
}
```

The chart workspace must not contain hard-coded switch statements scattered across components for every indicator.

One registry is the source of truth.

Each indicator owns:
- metadata
- input requirements
- calculation transform
- rendering config
- value formatter

## 10. Frequency Analyzer Contract

Canonical research formula:

```text
FA_raw = Volume / Frequency^3
```

Requirements:
- raw market volume stored as shares
- lots may be derived as shares / 100
- raw formula and visual normalization must be separate
- support both share-based and lot-based research series
- frequency <= 0 returns null, never Infinity
- missing data returns null
- negative impossible values must fail validation

Do not claim this is an official proprietary formula.

For chart rendering, raw values may be normalized separately using:
- rolling percentile
- z-score
- log transform

Any normalization must be clearly named and must not overwrite the raw value.

## 11. Market Data Contract

Required daily fields:

```text
ticker
trade_date
open
high
low
close
previous
volume_shares
value_idr
frequency
foreign_buy_shares nullable
foreign_sell_shares nullable
non_regular_volume_shares nullable
non_regular_value_idr nullable
non_regular_frequency nullable
source
ingested_at
```

Rules:
- preserve source units
- never silently convert
- use integer/decimal-safe DB types
- unique key on ticker + trade_date
- ingestion must be idempotent
- store data freshness metadata

## 12. Provider Architecture

Never couple frontend or analytics directly to Zapi.

Required provider interface:

```python
class MarketDataProvider(Protocol):
    async def get_stock_history(...): ...
    async def get_daily_market_summary(...): ...
```

Providers:

```text
providers/
├─ base.py
├─ zapi.py
└─ mock.py
```

Frontend must only speak to our backend API.

Backend provider flow:

```text
Zapi
  -> provider adapter
  -> validation/normalization
  -> Supabase Postgres
  -> analytics/services
  -> FastAPI
  -> Next.js
```

## 13. Supabase Rules

Use the connected Supabase integration when available.

For V0:
- Supabase is managed Postgres first
- do not add Auth
- do not add Storage
- do not add Realtime
- do not add Edge Functions unless explicitly requested

Create migrations for:
- stocks
- daily_market_data
- ingestion_runs

Recommended:
- index on stocks.ticker
- unique stocks.ticker
- unique daily_market_data(stock_id, trade_date)
- index daily_market_data(stock_id, trade_date desc)

If direct database access is used from FastAPI, keep privileged credentials server-side only.

No service-role key may appear in frontend bundles.

## 14. API Contract

Minimum endpoints:

```text
GET /health
GET /stocks
GET /stocks/{ticker}
GET /stocks/{ticker}/history
GET /data/status
```

History endpoint should be able to return:
- OHLC
- volume
- frequency
- raw Frequency Analyzer

Prefer one payload for synchronized chart panes rather than separate round trips per pane.

Example response shape:

```json
{
  "ticker": "ANTM",
  "from": "2026-01-01",
  "to": "2026-08-22",
  "latest_trade_date": "2026-08-22",
  "is_stale": false,
  "bars": [
    {
      "date": "2026-08-22",
      "open": 3100,
      "high": 3200,
      "low": 3080,
      "close": 3170,
      "volume_shares": 114080000,
      "frequency": 12345,
      "frequency_analyzer_raw_shares": 0.0000606
    }
  ]
}
```

## 15. Performance Budgets

Dashboard performance is a feature.

Targets:
- first usable workspace <= 2.5s on a normal broadband desktop
- ticker switch with cached data should feel immediate
- avoid full chart re-creation when a series update is sufficient
- no React state updates on every crosshair/pointer frame
- no expensive selectors over full history on every render
- memoize/derive intentionally
- lazy-load non-critical future modules
- chart resize should use ResizeObserver
- sparklines should be lightweight and bounded in point count
- watchlist may virtualize only when list size makes it necessary
- avoid loading full-market history into the browser

Do not pre-optimize with complex infrastructure.

## 16. State Model

Separate:

Server state:
- stock metadata
- historical bars
- data status
- watchlist data

Client UI state:
- active ticker
- watchlist collapsed
- watchlist width
- selected timeframe
- enabled indicators
- chart UI preferences

Do not duplicate server data into global client stores.

## 17. Loading / Empty / Error / Stale States

Every data-bound surface must handle:

Loading:
- skeleton shaped like final content
- chart loading overlay may be used without destroying previous chart if switching symbols

Empty:
- "No market data available for this symbol."

Error:
- concise error and retry action
- no raw stack trace

Stale:
- visible latest trading date
- show stale status if ingestion is behind expected market date
- stale data is still usable

## 18. Accessibility

Required:
- keyboard navigable controls
- focus-visible states
- sufficient contrast
- tooltips are not the only source of critical information
- icon buttons require accessible labels
- market direction is not encoded by color alone
- charts should have a textual active-symbol summary nearby

## 19. Security

Mandatory:
- never expose ZAPI_API_KEY to frontend
- never expose Supabase service-role key to frontend
- .env files gitignored
- .env.example contains names, not secrets
- validate ticker input
- parameterized DB queries
- backend CORS restricted appropriately
- no secrets in logs
- no secrets in committed fixtures

## 20. Git / Codex Workflow

Before implementation:
1. inspect repository
2. inspect AGENTS.md
3. inspect package manifests
4. inspect current git status
5. never overwrite unrelated user work

Implementation:
1. create/use feature branch
2. make smallest coherent changes
3. run tests continuously
4. keep commits coherent

Before commit:
1. run frontend lint
2. run TypeScript check
3. run frontend tests
4. run backend lint
5. run backend tests
6. review git diff
7. scan for secrets
8. verify no generated junk is tracked

Git rules:
- never force push
- never push directly to main
- never rewrite user commits
- never commit .env
- descriptive commit messages
- push current feature branch when authenticated
- create/update PR when supported

Suggested branch:
`codex/dashboard-v0`

Suggested commit families:
- `chore: initialize dashboard workspace`
- `feat: add Supabase market data schema`
- `feat: add watchlist and chart workspace`
- `feat: add frequency analyzer pane`
- `test: cover dashboard data flows`

## 21. Testing Matrix

Backend unit:
- FA 3000 / 2^3 = 375
- FA 3000 / 10^3 = 3
- frequency = 0 -> null
- duplicate ingestion -> upsert
- invalid OHLC rejected
- provider mapping correct

Frontend unit:
- watchlist row formatting
- ticker selection state
- stale badge logic
- indicator registry

Integration:
- API history payload loads into chart adapter
- ticker switch updates chart and header
- watchlist collapse triggers chart resize
- Frequency Analyzer pane aligns with price time scale

Playwright critical path:
1. open /app
2. default symbol appears
3. click a different ticker
4. header updates
5. candlestick chart updates
6. volume pane is visible
7. enable Frequency Analyzer
8. FA pane appears
9. collapse watchlist
10. chart expands
11. reload URL
12. selected ticker remains valid

## 22. Definition of Done

V0 is not done until:

- app boots from documented commands
- Supabase schema exists via reproducible migrations
- Zapi adapter is isolated behind provider interface
- actual or configured sample EOD data loads
- watchlist works
- ticker switching works
- sparkline works
- candlestick chart works
- volume pane works
- Frequency Analyzer works
- indicators menu works
- synchronized time scales work
- collapse/resizing works
- loading/empty/error/stale states work
- no secrets are committed
- lint passes
- type checks pass
- tests pass
- critical Playwright flow passes
- README setup is accurate
- Git diff is reviewed
- branch is committed and pushed when credentials allow

## 23. Agent Working Style

The agent must:
- prefer working software over decorative completeness
- avoid inventing data or unsupported APIs
- inspect existing code before replacing it
- keep modules small and composable
- preserve raw data
- document units
- fail visibly when assumptions are unknown
- ask only when a blocking decision cannot be inferred safely
- otherwise make the simplest reversible choice

When a provider or credential is unavailable:
- build the adapter and contract
- use explicit mock fixtures
- mark mock data visibly
- do not stall the entire dashboard build

## 24. Final Response Contract

At the end of each implementation task, report:

1. What changed
2. Files changed
3. Database changes
4. Tests run and results
5. Manual verification performed
6. Known limitations
7. Git branch
8. Commit hash
9. PR status
10. Exact next recommended task

Do not claim tests, commits, pushes, migrations, or deployments succeeded unless they actually did.
