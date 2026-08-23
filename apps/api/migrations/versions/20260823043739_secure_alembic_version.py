"""Restrict browser roles from Alembic's migration ledger.

Revision ID: 20260823043739
Revises: 20260822154827
"""

from pathlib import Path

from alembic import op

revision = "20260823043739"
down_revision = "20260822154827"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823043739_secure_alembic_version.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    """Keep the security restriction in place during application rollbacks."""
