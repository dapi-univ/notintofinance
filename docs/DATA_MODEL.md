# Dashboard V0 Data Model

The authoritative schema is the SQL migration under `supabase/migrations`.

- Prices and IDR values use exact `numeric` values.
- Volume and frequency use `bigint` source units.
- `volume_shares` always stores shares; lots are derived as `volume_shares / 100`.
- `daily_market_data` is unique on `(stock_id, trade_date)` for idempotent ingestion.
- `ingestion_runs` records provider, requested date, row counts, status, and any sanitized failure message.
- All timestamps use `timestamptz`.
