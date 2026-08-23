from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

from app.schemas.warehouse import (
    IngestionCursorState,
    InstrumentMappingRecord,
    OrderbookSnapshotRecord,
    RunningTradesPage,
    TradePrintRecord,
)
from app.services.warehouse import PluangIngestionService


class CursorRepository:
    def __init__(self) -> None:
        self.cursor_updates: list[dict[str, object]] = []
        self.blocked_datasets: set[str] = set()

    async def mapping(self, ticker: str) -> InstrumentMappingRecord:
        return InstrumentMappingRecord(
            ticker=ticker,
            provider_instrument_id="10020",
            provider_ticker=ticker,
            mapping_status="mapped",
        )

    async def ingestion_cursor(self, **_: object) -> IngestionCursorState:
        return IngestionCursorState(
            instrument_key="10020",
            session_date=date(2026, 8, 21),
            cursor_value="resume-cursor",
            high_water_mark="23034",
            status="running",
        )

    async def has_terminal_quality_block(self, **values: object) -> bool:
        return values["dataset"] in self.blocked_datasets

    @asynccontextmanager
    async def advisory_lock(self, _: str) -> AsyncIterator[None]:
        yield

    async def upsert_broker_flow(self, _: object) -> tuple[int, int]:
        return 0, 0

    async def update_cursor(self, **values: object) -> None:
        self.cursor_updates.append(values)

    async def upsert_trade_prints(self, _: object) -> tuple[int, int]:
        return 1, 0

    async def insert_orderbook_snapshot(self, _: object) -> int:
        return 1


class CursorProvider:
    async def get_broker_summary(self, *_: object) -> tuple[list[object], dict[str, object]]:
        return [], {}

    async def get_running_trades(
        self, *_: object, cursor: str | None = None
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        assert cursor == "resume-cursor"
        record = TradePrintRecord(
            ticker="BBCA",
            provider_sequence="23033",
            trade_date=date(2026, 8, 21),
            executed_at=datetime.fromisoformat("2026-08-21T15:49:58+07:00"),
            price=Decimal("6450"),
            lots=1,
            shares=100,
            aggressor_action="BUY",
        )
        return RunningTradesPage(records=[record], next_cursor="next-cursor"), {}

    async def get_orderbook(
        self, *_: object
    ) -> tuple[OrderbookSnapshotRecord, dict[str, object]]:
        return (
            OrderbookSnapshotRecord(
                ticker="BBCA",
                observed_at=datetime.fromisoformat("2026-08-23T07:01:33+00:00"),
                best_bid=None,
                best_ask=None,
                spread=None,
                levels=[],
            ),
            {},
        )


async def test_running_trade_canary_resumes_and_preserves_capped_cursor() -> None:
    repository = CursorRepository()
    service = PluangIngestionService(CursorProvider(), repository)  # type: ignore[arg-type]

    result = await service.collect_canary(
        ["BBCA"], trade_date=date(2026, 8, 21), max_pages=1
    )

    assert result[0].status == "partial"
    assert result[0].trade_pages == 1
    assert repository.cursor_updates[-1]["cursor_value"] == "next-cursor"
    assert repository.cursor_updates[-1]["status"] == "partial"


async def test_terminal_quality_event_blocks_only_affected_dataset() -> None:
    repository = CursorRepository()
    repository.blocked_datasets.add("finance:pluang/running-trades")
    service = PluangIngestionService(CursorProvider(), repository)  # type: ignore[arg-type]

    result = await service.collect_canary(
        ["BBCA"], trade_date=date(2026, 8, 21), max_pages=1
    )

    assert result[0].status == "blocked"
    assert result[0].error == "running-trades-blocked"
    assert result[0].trade_rows == 0
    assert result[0].trade_pages == 0
    assert repository.cursor_updates == []
