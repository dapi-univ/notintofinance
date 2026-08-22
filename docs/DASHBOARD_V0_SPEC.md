# Dashboard V0 Product Specification

## Objective

Ship a reliable first version of the stock research workspace before building any landing page.

The product is used primarily after IDX market close and may operate on delayed EOD data.

## Primary User Flow

1. Open `/app`.
2. See a compact navigation rail.
3. See a watchlist with Indonesian stocks and mini price sparklines.
4. Select a ticker.
5. Main chart updates without full page reload.
6. Inspect candlestick price and volume.
7. Open Indicators menu.
8. Enable Frequency Analyzer.
9. FA appears in a synchronized pane below price.
10. Collapse watchlist to enlarge chart.

## V0 Non-Goals

- real-time streaming
- landing page
- auth
- payment
- portfolio
- foreign scoring
- big matched transactions
- AI features
- broker flow
- screener implementation

## Reference Interaction Patterns

Use screenshots supplied by the product owner as interaction references:
- Stockbit: rail + watchlist + sparklines + chart workspace
- Bandar Metrics: analytics inside chart Indicators menu

Do not reproduce exact branding or visual assets.

## Data Source Strategy

Initial provider: Zapi.
Persistence: Supabase Postgres.

The frontend never calls Zapi directly.

Flow:

`Zapi -> FastAPI provider -> validation -> Supabase -> FastAPI -> Next.js`

## Core Tables

### stocks
- id
- ticker
- company_name
- sector
- subsector
- is_active
- created_at
- updated_at

### daily_market_data
- id
- stock_id
- trade_date
- open
- high
- low
- close
- previous
- volume_shares
- value_idr
- frequency
- foreign_buy_shares nullable
- foreign_sell_shares nullable
- non_regular_volume_shares nullable
- non_regular_value_idr nullable
- non_regular_frequency nullable
- source
- created_at
- updated_at

Unique:
- stocks.ticker
- daily_market_data(stock_id, trade_date)

### ingestion_runs
- id
- provider
- started_at
- finished_at
- status
- requested_date
- rows_received
- rows_inserted
- rows_updated
- error_message nullable

## Dashboard Components

- AppShell
- NavigationRail
- WatchlistPanel
- WatchlistSearch
- WatchlistItem
- MiniSparkline
- ChartWorkspace
- SymbolHeader
- ChartToolbar
- TimeframeSelector
- IndicatorMenu
- PricePane
- VolumePane
- IndicatorPaneManager
- FrequencyAnalyzerPane
- DataStatusBadge

## V0 Acceptance Criteria

- stock switching is functional
- chart and header stay synchronized
- watchlist collapse/resizing does not break chart
- mini sparklines render
- price candles render
- volume renders
- Frequency Analyzer renders
- all panes use the same date/time domain
- direct Zapi secrets never reach browser
- latest trade date is visible
- stale/error/empty states are handled
- unit tests and critical E2E pass
