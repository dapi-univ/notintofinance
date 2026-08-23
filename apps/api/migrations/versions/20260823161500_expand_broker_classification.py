"""Preserve the provider's observed BUMN broker classification.

Revision ID: 20260823161500
Revises: 20260823160000
"""

from pathlib import Path

from alembic import op

revision = "20260823161500"
down_revision = "20260823160000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823161500_expand_broker_classification.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute(
        "alter table public.broker_directory "
        "drop constraint broker_directory_classification_check, "
        "add constraint broker_directory_classification_check "
        "check (classification is null or classification in ('LOCAL', 'FOREIGN'))"
    )
