"""Backfill verified tradebook component availability from retained envelopes.

Revision ID: 20260823162000
Revises: 20260823161500
"""

from pathlib import Path

from alembic import op

revision = "20260823162000"
down_revision = "20260823161500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823162000_backfill_tradebook_session_availability.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    # Derived availability rows are retained on downgrade to avoid deleting observations.
    pass
