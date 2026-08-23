"""Remove warehouse FK indexes duplicated by leftmost composite indexes.

Revision ID: 20260823081000
Revises: 20260823080000
"""

from pathlib import Path

from alembic import op

revision = "20260823081000"
down_revision = "20260823080000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823081000_remove_redundant_warehouse_indexes.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute(
        "create index if not exists instrument_provider_mappings_stock_id_idx "
        "on public.instrument_provider_mappings (stock_id)"
    )
    op.execute(
        "create index if not exists broker_flow_daily_stock_id_idx "
        "on public.broker_flow_daily (stock_id)"
    )
    op.execute(
        "create index if not exists trade_prints_stock_id_idx "
        "on public.trade_prints (stock_id)"
    )
    op.execute(
        "create index if not exists orderbook_snapshots_stock_id_idx "
        "on public.orderbook_snapshots (stock_id)"
    )
    op.execute(
        "create index if not exists orderbook_levels_snapshot_id_idx "
        "on public.orderbook_levels (snapshot_id)"
    )
