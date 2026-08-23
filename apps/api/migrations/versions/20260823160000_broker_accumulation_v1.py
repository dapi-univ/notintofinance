"""Add session-safe microstructure metadata and broker directory.

Revision ID: 20260823160000
Revises: 20260823133000
"""

from pathlib import Path

from alembic import op

revision = "20260823160000"
down_revision = "20260823133000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823160000_broker_accumulation_v1.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute(
        "alter table public.trade_prints "
        "drop constraint trade_prints_session_binding_check, "
        "drop column gateway_observed_at, "
        "drop column session_binding_method, "
        "drop column provider_session_asserted"
    )
    op.execute("drop table if exists public.tradebook_collection_sessions cascade")
    op.execute("drop table if exists public.broker_directory cascade")
