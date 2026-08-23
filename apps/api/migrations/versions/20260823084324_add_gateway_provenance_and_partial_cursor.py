"""Add raw gateway provenance and resumable partial cursor status.

Revision ID: 20260823084324
Revises: 20260823081000
"""

from pathlib import Path

from alembic import op

revision = "20260823084324"
down_revision = "20260823081000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration = (
        Path(__file__).resolve().parents[4]
        / "supabase"
        / "migrations"
        / "20260823084324_add_gateway_provenance_and_partial_cursor.sql"
    )
    for statement in migration.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute(
        "update public.ingestion_cursors set status = 'running' where status = 'partial'"
    )
    op.execute(
        "alter table public.ingestion_cursors "
        "drop constraint ingestion_cursors_status_check"
    )
    op.execute(
        "alter table public.ingestion_cursors "
        "add constraint ingestion_cursors_status_check "
        "check (status in ('pending', 'running', 'succeeded', 'failed', 'exhausted'))"
    )
    op.execute(
        "alter table public.raw_provider_payloads "
        "drop constraint raw_provider_payloads_gateway_not_blank, "
        "drop constraint raw_provider_payloads_source_not_blank, "
        "drop column gateway, drop column source_provider"
    )
