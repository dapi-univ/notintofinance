alter table public.alembic_version enable row level security;
revoke all on table public.alembic_version from anon, authenticated;
