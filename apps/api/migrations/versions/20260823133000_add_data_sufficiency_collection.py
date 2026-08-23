"""Add data-sufficient EOD metadata, tradebook facts, and collection state.

Revision ID: 20260823133000
Revises: 20260823084324
"""

from pathlib import Path

from alembic import op

revision = "20260823133000"
down_revision = "20260823084324"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823133000_add_data_sufficiency_collection.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute(
        "alter table public.ingestion_cursors "
        "drop constraint ingestion_cursors_collection_floor_check, "
        "drop constraint ingestion_cursors_collection_counts_check, "
        "drop constraint ingestion_cursors_status_check, "
        "drop constraint ingestion_cursors_identity_key, "
        "drop column collection_filter, drop column collection_floor_idr, "
        "drop column rows_fetched, drop column rows_retained"
    )
    op.execute(
        "alter table public.ingestion_cursors "
        "add constraint ingestion_cursors_identity_key "
        "unique (provider, dataset, instrument_key), "
        "add constraint ingestion_cursors_status_check "
        "check (status in "
        "('pending', 'running', 'partial', 'succeeded', 'failed', 'exhausted'))"
    )
    op.execute("drop table if exists public.tradebook_aggregates cascade")
    op.execute(
        "alter table public.daily_market_data "
        "drop constraint daily_market_data_market_metadata_nonnegative, "
        "drop column listed_shares, drop column tradeable_shares, "
        "drop column weight_for_index, drop column index_individual"
    )
