import importlib.util
from pathlib import Path


def test_warehouse_migration_chain_and_security_contract() -> None:
    root = Path(__file__).resolve().parents[3]
    sql = (
        root / "supabase/migrations/20260823080000_shared_market_warehouse_v1.sql"
    ).read_text(encoding="utf-8")
    revision_path = (
        root
        / "apps/api/migrations/versions/20260823080000_shared_market_warehouse_v1.py"
    )
    spec = importlib.util.spec_from_file_location("warehouse_migration", revision_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "20260823080000"
    assert module.down_revision == "20260823043937"
    for table in (
        "instrument_provider_mappings",
        "provider_request_ledger",
        "raw_provider_payloads",
        "broker_flow_daily",
        "trade_prints",
        "orderbook_snapshots",
        "orderbook_levels",
        "data_quality_events",
        "ingestion_cursors",
    ):
        assert f"create table public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"revoke all on table public.{table} from anon, authenticated" in sql

    assert "shares = lots * 100" in sql
    assert "source_top_n" in sql
    assert "unique (stock_id, provider, trade_date, provider_sequence)" in sql

    cleanup_path = (
        root
        / "apps/api/migrations/versions/20260823081000_remove_redundant_warehouse_indexes.py"
    )
    cleanup_spec = importlib.util.spec_from_file_location(
        "warehouse_index_cleanup", cleanup_path
    )
    assert cleanup_spec and cleanup_spec.loader
    cleanup = importlib.util.module_from_spec(cleanup_spec)
    cleanup_spec.loader.exec_module(cleanup)
    assert cleanup.revision == "20260823081000"
    assert cleanup.down_revision == "20260823080000"
