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
uv run --project apps/api python -m app.warehouse_cli map --all-active --request-cap 1000 --daily-budget 1200 --concurrency 2
```

Both commands are idempotent. `--all-active` selects only missing or transient mappings by
default.

## Microstructure canary

```powershell
uv run --project apps/api python -m app.warehouse_cli canary AADI BBCA TLKM --max-pages 3 --request-cap 30
```

The session date defaults to the latest confirmed EOD date in PostgreSQL. Do not increase the
three-symbol, three-page or 30-request Phase 1 boundary before audit approval. A repeated run
continues a stored cursor for the same session rather than restarting its first page.
