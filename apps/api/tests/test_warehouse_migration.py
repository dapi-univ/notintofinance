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

    corrective_path = (
        root
        / "apps/api/migrations/versions/20260823084324_add_gateway_provenance_and_partial_cursor.py"
    )
    corrective_spec = importlib.util.spec_from_file_location(
        "warehouse_gateway_correction", corrective_path
    )
    assert corrective_spec and corrective_spec.loader
    corrective = importlib.util.module_from_spec(corrective_spec)
    corrective_spec.loader.exec_module(corrective)
    corrective_sql = (
        root
        / "supabase/migrations/20260823084324_add_gateway_provenance_and_partial_cursor.sql"
    ).read_text(encoding="utf-8")
    assert corrective.revision == "20260823084324"
    assert corrective.down_revision == "20260823081000"
    assert "add column gateway text" in corrective_sql
    assert "add column source_provider text" in corrective_sql
    assert "'partial'" in corrective_sql

    sufficiency_path = (
        root
        / "apps/api/migrations/versions/20260823133000_add_data_sufficiency_collection.py"
    )
    sufficiency_spec = importlib.util.spec_from_file_location(
        "data_sufficiency_collection", sufficiency_path
    )
    assert sufficiency_spec and sufficiency_spec.loader
    sufficiency = importlib.util.module_from_spec(sufficiency_spec)
    sufficiency_spec.loader.exec_module(sufficiency)
    sufficiency_sql = (
        root
        / "supabase/migrations/20260823133000_add_data_sufficiency_collection.sql"
    ).read_text(encoding="utf-8")
    assert sufficiency.revision == "20260823133000"
    assert sufficiency.down_revision == "20260823084324"
    assert "create table public.tradebook_aggregates" in sufficiency_sql
    assert "alter table public.tradebook_aggregates enable row level security" in sufficiency_sql
    assert "revoke all on table public.tradebook_aggregates" in sufficiency_sql
    assert "unique nulls not distinct" in sufficiency_sql
    assert "collection_filter jsonb" in sufficiency_sql
    assert "rows_retained <= rows_fetched" in sufficiency_sql
