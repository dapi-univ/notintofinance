create table public.instrument_provider_mappings (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  provider text not null,
  provider_instrument_id text,
  provider_ticker text not null,
  exchange text not null,
  mapping_status text not null,
  first_observed_at timestamptz not null default now(),
  last_observed_at timestamptz not null default now(),
  source text not null,
  constraint instrument_provider_mappings_stock_provider_key unique (stock_id, provider),
  constraint instrument_provider_mappings_provider_not_blank check (length(btrim(provider)) > 0),
  constraint instrument_provider_mappings_ticker_not_blank check (length(btrim(provider_ticker)) > 0),
  constraint instrument_provider_mappings_exchange_not_blank check (length(btrim(exchange)) > 0),
  constraint instrument_provider_mappings_source_not_blank check (length(btrim(source)) > 0),
  constraint instrument_provider_mappings_status_check
    check (mapping_status in ('mapped', 'unsupported', 'ambiguous', 'transient_failure')),
  constraint instrument_provider_mappings_mapped_id_check
    check (mapping_status <> 'mapped' or provider_instrument_id is not null)
);

create unique index instrument_provider_mappings_provider_id_key
  on public.instrument_provider_mappings (provider, provider_instrument_id)
  where provider_instrument_id is not null;
create index instrument_provider_mappings_provider_status_idx
  on public.instrument_provider_mappings (provider, mapping_status, stock_id);

create table public.provider_request_ledger (
  id bigint generated always as identity primary key,
  provider text not null,
  dataset text not null,
  endpoint_name text not null,
  request_fingerprint text not null,
  requested_at timestamptz not null,
  completed_at timestamptz,
  status_code integer,
  latency_ms integer,
  attempt_number integer not null,
  quota_limit integer,
  quota_remaining_minute integer,
  quota_remaining_month integer,
  plan_expired boolean,
  cache_status text,
  rows_received integer,
  error_class text,
  warning text,
  constraint provider_request_ledger_attempt_positive check (attempt_number > 0),
  constraint provider_request_ledger_latency_nonnegative check (latency_ms is null or latency_ms >= 0),
  constraint provider_request_ledger_rows_nonnegative check (rows_received is null or rows_received >= 0),
  constraint provider_request_ledger_quota_nonnegative check (
    (quota_limit is null or quota_limit >= 0)
    and (quota_remaining_minute is null or quota_remaining_minute >= 0)
    and (quota_remaining_month is null or quota_remaining_month >= 0)
  )
);

create index provider_request_ledger_provider_dataset_requested_idx
  on public.provider_request_ledger (provider, dataset, requested_at desc);
create index provider_request_ledger_provider_requested_idx
  on public.provider_request_ledger (provider, requested_at desc);

create table public.raw_provider_payloads (
  id bigint generated always as identity primary key,
  provider text not null,
  dataset text not null,
  instrument_key text,
  date_from date,
  date_to date,
  cursor_value text,
  response_hash text not null,
  payload jsonb not null,
  fetched_at timestamptz not null default now(),
  expires_at timestamptz not null,
  normalization_status text not null default 'staged',
  normalization_error text,
  constraint raw_provider_payloads_provider_hash_key unique (provider, dataset, response_hash),
  constraint raw_provider_payloads_status_check
    check (normalization_status in ('staged', 'normalized', 'rejected')),
  constraint raw_provider_payloads_expiry_check check (expires_at > fetched_at)
);

create index raw_provider_payloads_expiry_idx on public.raw_provider_payloads (expires_at);
create index raw_provider_payloads_lookup_idx
  on public.raw_provider_payloads (provider, dataset, instrument_key, fetched_at desc);

create table public.broker_flow_daily (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  trade_date_from date not null,
  trade_date_to date not null,
  broker_code text not null,
  broker_name text,
  side text not null,
  rank integer not null,
  lots bigint not null,
  shares bigint not null,
  value_idr numeric(24, 2) not null,
  average_price numeric(18, 4) not null,
  provider text not null,
  source_scope text not null,
  source_top_n integer,
  ingested_at timestamptz not null default now(),
  constraint broker_flow_daily_identity_key
    unique (stock_id, provider, trade_date_from, trade_date_to, side, broker_code),
  constraint broker_flow_daily_date_range_check check (trade_date_to >= trade_date_from),
  constraint broker_flow_daily_side_check check (side in ('BUY', 'SELL')),
  constraint broker_flow_daily_rank_positive check (rank > 0),
  constraint broker_flow_daily_numbers_nonnegative
    check (lots >= 0 and shares >= 0 and value_idr >= 0 and average_price >= 0),
  constraint broker_flow_daily_share_conversion_check check (shares = lots * 100),
  constraint broker_flow_daily_scope_check check (source_scope in ('top_n', 'complete', 'unknown')),
  constraint broker_flow_daily_top_n_check
    check ((source_scope = 'top_n' and source_top_n is not null and source_top_n > 0)
      or (source_scope <> 'top_n'))
);

create index broker_flow_daily_stock_date_idx
  on public.broker_flow_daily (stock_id, trade_date_to desc, side, rank);

create table public.trade_prints (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  provider text not null,
  provider_sequence text not null,
  trade_date date not null,
  executed_at timestamptz not null,
  price numeric(18, 4) not null,
  lots bigint not null,
  shares bigint not null,
  aggressor_action text,
  fetched_at timestamptz not null default now(),
  constraint trade_prints_identity_key unique (stock_id, provider, trade_date, provider_sequence),
  constraint trade_prints_price_positive check (price > 0),
  constraint trade_prints_volume_nonnegative check (lots >= 0 and shares >= 0),
  constraint trade_prints_share_conversion_check check (shares = lots * 100),
  constraint trade_prints_action_check
    check (aggressor_action is null or aggressor_action in ('BUY', 'SELL', 'UNKNOWN'))
);

create index trade_prints_stock_date_time_idx
  on public.trade_prints (stock_id, trade_date desc, executed_at desc, id desc);

create table public.orderbook_snapshots (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  provider text not null,
  observed_at timestamptz not null,
  best_bid numeric(18, 4),
  best_ask numeric(18, 4),
  spread numeric(18, 4),
  fetched_at timestamptz not null default now(),
  constraint orderbook_snapshots_identity_key unique (stock_id, provider, observed_at),
  constraint orderbook_snapshots_prices_positive check (
    (best_bid is null or best_bid > 0)
    and (best_ask is null or best_ask > 0)
    and (spread is null or spread >= 0)
  )
);

create index orderbook_snapshots_stock_observed_idx
  on public.orderbook_snapshots (stock_id, observed_at desc);

create table public.orderbook_levels (
  id bigint generated always as identity primary key,
  snapshot_id bigint not null references public.orderbook_snapshots(id) on delete cascade,
  side text not null,
  level_rank integer not null,
  price numeric(18, 4) not null,
  lots bigint not null,
  constraint orderbook_levels_identity_key unique (snapshot_id, side, level_rank),
  constraint orderbook_levels_side_check check (side in ('BID', 'ASK')),
  constraint orderbook_levels_rank_positive check (level_rank > 0),
  constraint orderbook_levels_values_check check (price > 0 and lots >= 0)
);

create table public.data_quality_events (
  id bigint generated always as identity primary key,
  provider text not null,
  dataset text not null,
  stock_id bigint references public.stocks(id) on delete cascade,
  severity text not null,
  reason_code text not null,
  context jsonb not null default '{}'::jsonb,
  retryable boolean not null,
  attempt_count integer not null default 1,
  next_retry_at timestamptz,
  is_terminal boolean not null,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  constraint data_quality_events_severity_check check (severity in ('info', 'warning', 'error')),
  constraint data_quality_events_attempt_positive check (attempt_count > 0)
);

create index data_quality_events_stock_id_idx on public.data_quality_events (stock_id);
create index data_quality_events_dataset_status_idx
  on public.data_quality_events (provider, dataset, is_terminal, next_retry_at);

create table public.ingestion_cursors (
  id bigint generated always as identity primary key,
  provider text not null,
  dataset text not null,
  stock_id bigint references public.stocks(id) on delete cascade,
  instrument_key text not null,
  session_date date,
  cursor_value text,
  high_water_mark text,
  status text not null,
  attempt_count integer not null default 1,
  next_retry_at timestamptz,
  error_message text,
  updated_at timestamptz not null default now(),
  constraint ingestion_cursors_identity_key unique (provider, dataset, instrument_key),
  constraint ingestion_cursors_status_check
    check (status in ('pending', 'running', 'succeeded', 'failed', 'exhausted')),
  constraint ingestion_cursors_attempt_positive check (attempt_count > 0)
);

create index ingestion_cursors_stock_id_idx on public.ingestion_cursors (stock_id);
create index ingestion_cursors_dataset_status_idx
  on public.ingestion_cursors (provider, dataset, status, next_retry_at);

alter table public.instrument_provider_mappings enable row level security;
alter table public.provider_request_ledger enable row level security;
alter table public.raw_provider_payloads enable row level security;
alter table public.broker_flow_daily enable row level security;
alter table public.trade_prints enable row level security;
alter table public.orderbook_snapshots enable row level security;
alter table public.orderbook_levels enable row level security;
alter table public.data_quality_events enable row level security;
alter table public.ingestion_cursors enable row level security;

revoke all on table public.instrument_provider_mappings from anon, authenticated;
revoke all on table public.provider_request_ledger from anon, authenticated;
revoke all on table public.raw_provider_payloads from anon, authenticated;
revoke all on table public.broker_flow_daily from anon, authenticated;
revoke all on table public.trade_prints from anon, authenticated;
revoke all on table public.orderbook_snapshots from anon, authenticated;
revoke all on table public.orderbook_levels from anon, authenticated;
revoke all on table public.data_quality_events from anon, authenticated;
revoke all on table public.ingestion_cursors from anon, authenticated;

revoke all on sequence public.instrument_provider_mappings_id_seq from anon, authenticated;
revoke all on sequence public.provider_request_ledger_id_seq from anon, authenticated;
revoke all on sequence public.raw_provider_payloads_id_seq from anon, authenticated;
revoke all on sequence public.broker_flow_daily_id_seq from anon, authenticated;
revoke all on sequence public.trade_prints_id_seq from anon, authenticated;
revoke all on sequence public.orderbook_snapshots_id_seq from anon, authenticated;
revoke all on sequence public.orderbook_levels_id_seq from anon, authenticated;
revoke all on sequence public.data_quality_events_id_seq from anon, authenticated;
revoke all on sequence public.ingestion_cursors_id_seq from anon, authenticated;
