from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.services.trade_cursor import encode_trade_cursor
from app.services.warehouse_read import WarehouseReadService


class CompositeCursorRepository:
    def __init__(self) -> None:
        base = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
        self.rows = [
            _row(5, base + timedelta(minutes=5)),
            _row(100, base + timedelta(minutes=4)),
            _row(2, base + timedelta(minutes=3)),
            _row(80, base + timedelta(minutes=2)),
            _row(1, base + timedelta(minutes=1)),
        ]

    async def trades(
        self,
        ticker: str,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        cursor: tuple[datetime, int] | None,
    ) -> list[SimpleNamespace]:
        assert ticker == "BBCA"
        assert date_from == date_to == date(2026, 8, 21)
        rows = sorted(self.rows, key=lambda row: (row.executed_at, row.id), reverse=True)
        if cursor:
            rows = [row for row in rows if (row.executed_at, row.id) < cursor]
        return rows[:limit]


def _row(row_id: int, executed_at: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        provider_sequence=str(row_id),
        trade_date=date(2026, 8, 21),
        executed_at=executed_at,
        price=Decimal("6400"),
        lots=1,
        shares=100,
        aggressor_action="BUY",
        provider="pluang",
    )


async def test_composite_trade_cursor_returns_every_row_once_in_stable_order() -> None:
    repository = CompositeCursorRepository()
    service = WarehouseReadService(repository)  # type: ignore[arg-type]
    cursor: str | None = None
    seen: list[int] = []

    while True:
        response = await service.trades(
            "BBCA",
            date(2026, 8, 21),
            date(2026, 8, 21),
            limit=2,
            cursor=cursor,
        )
        seen.extend(row.id for row in response.rows)
        cursor = response.next_cursor
        if cursor is None:
            break

    expected = [row.id for row in repository.rows]
    assert seen == expected
    assert len(seen) == len(set(seen))

    last = repository.rows[-1]
    empty = await service.trades(
        "BBCA",
        date(2026, 8, 21),
        date(2026, 8, 21),
        limit=2,
        cursor=encode_trade_cursor(last.executed_at, last.id),
    )
    assert empty.rows == []
    assert empty.next_cursor is None
