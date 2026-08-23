# Shared Market Warehouse Phase 1 Operations

Run commands from the repository root. Environment values are loaded through application
`Settings`; commands never echo credentials.

## Migrations

```powershell
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

## Zapi EOD

Dry-run the pending-first selection:

```powershell
uv run --project apps/api python -m app.cli --resume --skip-universe-sync --dry-run
```

Run a ten-symbol canary:

```powershell
uv run --project apps/api python -m app.cli --resume --skip-universe-sync --max-symbols 10 --request-cap 10 --concurrency 2
```

Resume eligible work (unattempted first, then retryable failures):

```powershell
uv run --project apps/api python -m app.cli --resume --skip-universe-sync --request-cap 800 --concurrency 2
```

Terminal data-quality failures are excluded. Retrying them requires the explicit
`--include-terminal` switch.

## Pluang mappings

```powershell
uv run --project apps/api python -m app.warehouse_cli map AADI BBCA TLKM --request-cap 3
```

Mapping is optional cached metadata. Normalized `finance:pluang` endpoints accept canonical
IDX tickers directly and do not require a universe-wide resolve pass.

## Microstructure canary

```powershell
uv run --project apps/api python -m app.warehouse_cli canary AADI BBCA TLKM --max-pages 1 --request-cap 9 --compare-existing
```

The session date defaults to the latest confirmed EOD date in PostgreSQL. The comparison
canary reads one page from the start without replacing the previously persisted continuation
cursor or writing normalized warehouse facts. A successful full-overlap comparison resolves
only its matching unresolved comparison event. Ordinary bounded runs resume the stored Zapi
`nextCursor`; reaching the page cap with a remaining cursor exits as `partial`, never
`running`. An unresolved terminal comparison event blocks only its affected dataset during
ordinary runs; use `--compare-existing` to perform a bounded re-check after review. Do not
increase the three-symbol, three-page or 30-request Phase 1 boundary before audit approval.

## Test database safety

Pytest processes cannot construct a `Database` for a managed Supabase hostname. PostgreSQL
tests must use an isolated local database or mocks. Synthetic trade identities beginning with
`FIXTURE-`, `SYNTHETIC-`, or `TEST-` are also rejected by managed-Supabase repository writes.
