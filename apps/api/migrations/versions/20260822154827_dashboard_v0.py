"""Apply the authoritative Dashboard V0 Supabase schema.

Revision ID: 20260822154827
Revises: None
"""

from pathlib import Path

from alembic import op

revision = "20260822154827"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260822154827_dashboard_v0.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists public.ingestion_runs cascade")
    op.execute("drop table if exists public.daily_market_data cascade")
    op.execute("drop table if exists public.stocks cascade")
