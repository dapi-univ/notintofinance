# Alembic Model Drift Audit

Audited against the live PostgreSQL schema at Alembic head `20260823084324` on
2026-08-23. No migration was generated or applied for this audit.

`alembic check` reports 84 operations. These are metadata-representation drift: the live
database contains migration-defined constraints, indexes, and comments that are not declared
in SQLAlchemy `Base.metadata`. There is no missing live column, type mismatch, nullability
mismatch, or unapplied revision. Applying the generated removal operations would weaken the
schema and is not safe.

## Classification

- 53 `remove_constraint` operations are live check constraints omitted from ORM metadata.
- 10 `remove_constraint` operations are live unique constraints omitted from ORM metadata.
- 16 `remove_index` operations are live named indexes omitted from ORM metadata.
- 3 `add_index` operations come from ORM `index=True` declarations whose generated `ix_*`
  identities do not match the deliberate migration-defined index or unique-constraint shape.
- 2 `modify_comment` operations would remove live column comments omitted from ORM metadata.

An enhanced comparison with server-default checking enabled additionally reports 21 live
defaults omitted from ORM metadata. Standard `alembic check` does not currently include those
items because `compare_server_default` is not enabled.

## Exact standard-check items

### Check constraints present live but absent from ORM metadata (53)

- `broker_flow_daily`: `broker_flow_daily_date_range_check`,
  `broker_flow_daily_numbers_nonnegative`, `broker_flow_daily_rank_positive`,
  `broker_flow_daily_scope_check`, `broker_flow_daily_share_conversion_check`,
  `broker_flow_daily_side_check`, `broker_flow_daily_top_n_check`.
- `daily_market_data`: `daily_market_data_foreign_buy_nonnegative`,
  `daily_market_data_foreign_sell_nonnegative`, `daily_market_data_frequency_nonnegative`,
  `daily_market_data_non_regular_frequency_nonnegative`,
  `daily_market_data_non_regular_value_nonnegative`,
  `daily_market_data_non_regular_volume_nonnegative`, `daily_market_data_ohlc_valid`,
  `daily_market_data_prices_positive`, `daily_market_data_source_not_blank`,
  `daily_market_data_value_nonnegative`, `daily_market_data_volume_nonnegative`.
- `data_quality_events`: `data_quality_events_attempt_positive`,
  `data_quality_events_severity_check`.
- `ingestion_checkpoints`: `ingestion_checkpoints_dataset_not_blank`,
  `ingestion_checkpoints_provider_not_blank`, `ingestion_checkpoints_status_check`.
- `ingestion_cursors`: `ingestion_cursors_attempt_positive`,
  `ingestion_cursors_status_check`.
- `ingestion_runs`: `ingestion_runs_counts_nonnegative`,
  `ingestion_runs_finished_after_started`, `ingestion_runs_provider_not_blank`,
  `ingestion_runs_status_valid`.
- `instrument_provider_mappings`: `instrument_provider_mappings_exchange_not_blank`,
  `instrument_provider_mappings_mapped_id_check`,
  `instrument_provider_mappings_provider_not_blank`,
  `instrument_provider_mappings_source_not_blank`,
  `instrument_provider_mappings_status_check`,
  `instrument_provider_mappings_ticker_not_blank`.
- `orderbook_levels`: `orderbook_levels_rank_positive`, `orderbook_levels_side_check`,
  `orderbook_levels_values_check`.
- `orderbook_snapshots`: `orderbook_snapshots_prices_positive`.
- `provider_request_ledger`: `provider_request_ledger_attempt_positive`,
  `provider_request_ledger_latency_nonnegative`,
  `provider_request_ledger_quota_nonnegative`, `provider_request_ledger_rows_nonnegative`.
- `raw_provider_payloads`: `raw_provider_payloads_expiry_check`,
  `raw_provider_payloads_gateway_not_blank`, `raw_provider_payloads_source_not_blank`,
  `raw_provider_payloads_status_check`.
- `stocks`: `stocks_company_name_not_blank`, `stocks_ticker_format`.
- `trade_prints`: `trade_prints_action_check`, `trade_prints_price_positive`,
  `trade_prints_share_conversion_check`, `trade_prints_volume_nonnegative`.

### Unique constraints present live but absent from ORM metadata (10)

- `broker_flow_daily_identity_key`
- `daily_market_data_stock_date_key`
- `ingestion_checkpoints_identity_key`
- `ingestion_cursors_identity_key`
- `instrument_provider_mappings_stock_provider_key`
- `orderbook_levels_identity_key`
- `orderbook_snapshots_identity_key`
- `raw_provider_payloads_provider_hash_key`
- `stocks_ticker_key`
- `trade_prints_identity_key`

### Named indexes present live but absent from ORM metadata (16)

- `broker_flow_daily_stock_date_idx`
- `daily_market_data_stock_date_desc_idx`
- `data_quality_events_dataset_status_idx`
- `data_quality_events_stock_id_idx`
- `ingestion_checkpoints_stock_id_idx`
- `ingestion_cursors_dataset_status_idx`
- `ingestion_cursors_stock_id_idx`
- `ingestion_runs_started_at_desc_idx`
- `instrument_provider_mappings_provider_id_key`
- `instrument_provider_mappings_provider_status_idx`
- `orderbook_snapshots_stock_observed_idx`
- `provider_request_ledger_provider_dataset_requested_idx`
- `provider_request_ledger_provider_requested_idx`
- `raw_provider_payloads_expiry_idx`
- `raw_provider_payloads_lookup_idx`
- `trade_prints_stock_date_time_idx`

### ORM-generated indexes absent from the live schema (3)

- `ix_daily_market_data_stock_id`
- `ix_ingestion_checkpoints_stock_id`
- `ix_stocks_ticker`

These do not demonstrate missing indexing. The live schema already uses the deliberate named
composite indexes or unique constraint covering the corresponding access path.

### Live comments omitted from ORM metadata (2)

- `daily_market_data.volume_shares`
- `daily_market_data.frequency`

### Additional server defaults omitted from ORM metadata (21)

- Identity defaults on `id` for: `broker_flow_daily`, `daily_market_data`,
  `data_quality_events`, `ingestion_checkpoints`, `ingestion_cursors`, `ingestion_runs`,
  `instrument_provider_mappings`, `orderbook_levels`, `orderbook_snapshots`,
  `provider_request_ledger`, `raw_provider_payloads`, `stocks`, and `trade_prints`.
- `data_quality_events.context` and `data_quality_events.attempt_count`.
- `ingestion_cursors.attempt_count`.
- `ingestion_runs.rows_received`, `ingestion_runs.rows_inserted`, and
  `ingestion_runs.rows_updated`.
- `raw_provider_payloads.normalization_status`.
- `stocks.is_active`.

## Required follow-up before schema expansion

Align SQLAlchemy metadata with the authoritative migration-defined schema, including names,
comments, and server defaults, then rerun autogenerate comparison. This is a metadata cleanup;
it must not be implemented by dropping the live protections or creating duplicate indexes.
