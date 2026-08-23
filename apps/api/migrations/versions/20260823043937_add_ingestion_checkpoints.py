"""Add resumable EOD ingestion checkpoints.

Revision ID: 20260823043937
Revises: 20260823043739
"""

from pathlib import Path

from alembic import op

revision = "20260823043937"
down_revision = "20260823043739"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823043937_add_ingestion_checkpoints.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists public.ingestion_checkpoints cascade")
