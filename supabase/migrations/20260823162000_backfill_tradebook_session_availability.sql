insert into public.tradebook_collection_sessions (
  stock_id,
  provider,
  trade_date,
  price_available,
  time_available,
  volume_available,
  processed_successfully,
  gateway_observed_at,
  session_binding_method,
  provider_session_asserted
)
select
  s.id,
  'pluang',
  r.date_from,
  jsonb_array_length(r.payload->'data'->'byPrice') > 0,
  jsonb_array_length(r.payload->'data'->'byTime') > 0,
  jsonb_array_length(r.payload->'data'->'byVolume') > 0,
  true,
  (r.payload->>'timestamp')::timestamptz,
  'confirmed_latest_eod',
  false
from public.raw_provider_payloads r
join public.stocks s on s.ticker = r.instrument_key
where r.dataset = 'finance:pluang/tradebook'
  and r.normalization_status = 'normalized'
  and r.date_from = r.date_to
  and r.date_from = (select max(trade_date) from public.daily_market_data)
  and jsonb_typeof(r.payload->'data'->'byPrice') = 'array'
  and jsonb_typeof(r.payload->'data'->'byTime') = 'array'
  and jsonb_typeof(r.payload->'data'->'byVolume') = 'array'
  and exists (
    select 1
    from public.daily_market_data d
    where d.stock_id = s.id and d.trade_date = r.date_from
  )
on conflict on constraint tradebook_collection_sessions_identity_key do update
set price_available = excluded.price_available,
    time_available = excluded.time_available,
    volume_available = excluded.volume_available,
    processed_successfully = excluded.processed_successfully,
    gateway_observed_at = excluded.gateway_observed_at,
    session_binding_method = excluded.session_binding_method,
    provider_session_asserted = excluded.provider_session_asserted,
    ingested_at = now();
