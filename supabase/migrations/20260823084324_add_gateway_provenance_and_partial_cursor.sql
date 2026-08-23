alter table public.raw_provider_payloads
  add column gateway text,
  add column source_provider text;

update public.raw_provider_payloads
set
  gateway = case when provider = 'zapi' then 'zapi' else 'direct' end,
  source_provider = case when provider = 'zapi' then 'idx' else provider end;

alter table public.raw_provider_payloads
  alter column gateway set not null,
  alter column source_provider set not null,
  add constraint raw_provider_payloads_gateway_not_blank
    check (length(btrim(gateway)) > 0),
  add constraint raw_provider_payloads_source_not_blank
    check (length(btrim(source_provider)) > 0);

alter table public.ingestion_cursors
  drop constraint ingestion_cursors_status_check,
  add constraint ingestion_cursors_status_check
    check (status in ('pending', 'running', 'partial', 'succeeded', 'failed', 'exhausted'));

update public.ingestion_cursors
set status = 'partial', updated_at = now()
where provider = 'pluang'
  and dataset = 'running-trades'
  and status = 'running'
  and cursor_value is not null;
