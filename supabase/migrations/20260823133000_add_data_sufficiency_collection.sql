alter table public.daily_market_data
  add column listed_shares bigint,
  add column tradeable_shares bigint,
  add column weight_for_index bigint,
  add column index_individual numeric(24, 6),
  add constraint daily_market_data_market_metadata_nonnegative check (
    (listed_shares is null or listed_shares >= 0)
    and (tradeable_shares is null or tradeable_shares >= 0)
    and (weight_for_index is null or weight_for_index >= 0)
    and (index_individual is null or index_individual >= 0)
  );

create table public.tradebook_aggregates (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  provider text not null,
  trade_date date not null,
  view_type text not null,
  bucket_key text not null,
  price numeric(18, 4),
  time_bucket text,
  buy_frequency bigint,
  buy_lots bigint,
  sell_frequency bigint,
  sell_lots bigint,
  pre_frequency bigint,
  pre_lots bigint,
  post_frequency bigint,
  post_lots bigint,
  total_frequency bigint,
  total_lots bigint,
  source_scope text not null,
  ingested_at timestamptz not null default now(),
  constraint tradebook_aggregates_identity_key
    unique (stock_id, provider, trade_date, view_type, bucket_key),
  constraint tradebook_aggregates_view_check check (view_type in ('price', 'time', 'volume')),
  constraint tradebook_aggregates_bucket_not_blank check (length(btrim(bucket_key)) > 0),
  constraint tradebook_aggregates_price_positive check (price is null or price > 0),
  constraint tradebook_aggregates_values_nonnegative check (
    (buy_frequency is null or buy_frequency >= 0)
    and (buy_lots is null or buy_lots >= 0)
    and (sell_frequency is null or sell_frequency >= 0)
    and (sell_lots is null or sell_lots >= 0)
    and (pre_frequency is null or pre_frequency >= 0)
    and (pre_lots is null or pre_lots >= 0)
    and (post_frequency is null or post_frequency >= 0)
    and (post_lots is null or post_lots >= 0)
    and (total_frequency is null or total_frequency >= 0)
    and (total_lots is null or total_lots >= 0)
  ),
  constraint tradebook_aggregates_scope_check check (source_scope = 'provider_aggregate')
);

create index tradebook_aggregates_stock_date_idx
  on public.tradebook_aggregates (stock_id, trade_date desc, view_type, bucket_key);

alter table public.tradebook_aggregates enable row level security;
revoke all on table public.tradebook_aggregates from anon, authenticated;
revoke all on sequence public.tradebook_aggregates_id_seq from anon, authenticated;

alter table public.ingestion_cursors
  drop constraint ingestion_cursors_identity_key,
  drop constraint ingestion_cursors_status_check,
  add column collection_filter jsonb not null default '{}'::jsonb,
  add column collection_floor_idr numeric(24, 2),
  add column rows_fetched bigint not null default 0,
  add column rows_retained bigint not null default 0,
  add constraint ingestion_cursors_identity_key
    unique nulls not distinct (provider, dataset, instrument_key, session_date),
  add constraint ingestion_cursors_status_check check (
    status in (
      'pending', 'running', 'partial', 'succeeded', 'failed', 'exhausted',
      'complete', 'blocked'
    )
  ),
  add constraint ingestion_cursors_collection_counts_check check (
    rows_fetched >= 0 and rows_retained >= 0 and rows_retained <= rows_fetched
  ),
  add constraint ingestion_cursors_collection_floor_check check (
    collection_floor_idr is null or collection_floor_idr >= 0
  );
