from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import URL

from app.db.session import Database, UnsafeDatabaseTarget, is_managed_supabase_url
from app.repositories.warehouse import PostgresWarehouseRepository
from app.schemas.warehouse import TradePrintRecord


def test_fixture_test_cannot_connect_to_managed_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "fixture-backed-write")
    production_url = URL.create(
        "postgresql",
        username="postgres.fixture",
        password="fixture-password",
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
    ).render_as_string(hide_password=False)

    with pytest.raises(UnsafeDatabaseTarget, match="isolated local test database or mocks"):
        Database(production_url)


def test_local_test_database_is_not_classified_as_managed_supabase() -> None:
    assert not is_managed_supabase_url("sqlite+aiosqlite:///:memory:")


async def test_synthetic_trade_identity_cannot_write_to_supabase_outside_pytest_guard() -> None:
    database = SimpleNamespace(is_managed_supabase=True)
    repository = PostgresWarehouseRepository(database)  # type: ignore[arg-type]
    record = TradePrintRecord(
        ticker="BBCA",
        provider_sequence="FIXTURE-BBCA-001",
        trade_date=date(2099, 1, 1),
        executed_at=datetime.fromisoformat("2099-01-01T12:00:00+07:00"),
        price=Decimal("1"),
        lots=1,
        shares=100,
        aggressor_action="BUY",
    )

    with pytest.raises(UnsafeDatabaseTarget, match="synthetic trade identities"):
        await repository.upsert_trade_prints([record])
