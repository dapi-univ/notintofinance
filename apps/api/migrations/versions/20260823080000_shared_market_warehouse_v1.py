"""Add the Phase 1 shared market warehouse foundation.

Revision ID: 20260823080000
Revises: 20260823043937
"""

from pathlib import Path

from alembic import op

revision = "20260823080000"
down_revision = "20260823043937"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823080000_shared_market_warehouse_v1.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in (
        "ingestion_cursors",
        "data_quality_events",
        "orderbook_levels",
        "orderbook_snapshots",
        "trade_prints",
        "broker_flow_daily",
        "raw_provider_payloads",
        "provider_request_ledger",
        "instrument_provider_mappings",
    ):
        op.execute(f"drop table if exists public.{table} cascade")
