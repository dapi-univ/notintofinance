create table public.broker_directory (
  id bigint generated always as identity primary key,
  broker_code text not null,
  broker_name text not null,
  classification text,
  gateway text not null,
  source_provider text not null,
  source_observed_at timestamptz not null,
  ingested_at timestamptz not null default now(),
  constraint broker_directory_identity_key unique (source_provider, broker_code),
  constraint broker_directory_code_not_blank check (length(btrim(broker_code)) > 0),
  constraint broker_directory_name_not_blank check (length(btrim(broker_name)) > 0),
  constraint broker_directory_gateway_not_blank check (length(btrim(gateway)) > 0),
  constraint broker_directory_source_not_blank check (length(btrim(source_provider)) > 0),
  constraint broker_directory_classification_check
    check (classification is null or classification in ('LOCAL', 'FOREIGN'))
);

create table public.tradebook_collection_sessions (
  id bigint generated always as identity primary key,
  stock_id bigint not null references public.stocks(id) on delete cascade,
  provider text not null,
  trade_date date not null,
  price_available boolean not null,
  time_available boolean not null,
  volume_available boolean not null,
  processed_successfully boolean not null,
  gateway_observed_at timestamptz not null,
  session_binding_method text not null,
  provider_session_asserted boolean not null default false,
  ingested_at timestamptz not null default now(),
  constraint tradebook_collection_sessions_identity_key
    unique (stock_id, provider, trade_date),
  constraint tradebook_collection_sessions_binding_check
    check (session_binding_method = 'confirmed_latest_eod')
);

create index tradebook_collection_sessions_stock_date_idx
  on public.tradebook_collection_sessions (stock_id, trade_date desc);

alter table public.trade_prints
  add column gateway_observed_at timestamptz,
  add column session_binding_method text,
  add column provider_session_asserted boolean not null default false,
  add constraint trade_prints_session_binding_check check (
    session_binding_method is null or session_binding_method = 'confirmed_latest_eod'
  );

alter table public.broker_directory enable row level security;
alter table public.tradebook_collection_sessions enable row level security;

revoke all on table public.broker_directory from anon, authenticated;
revoke all on table public.tradebook_collection_sessions from anon, authenticated;
revoke all on sequence public.broker_directory_id_seq from anon, authenticated;
revoke all on sequence public.tradebook_collection_sessions_id_seq from anon, authenticated;
