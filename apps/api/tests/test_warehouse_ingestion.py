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
            high_water_mark="FIXTURE-CURSOR-002",
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
            provider_sequence="FIXTURE-CURSOR-001",
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


class ComparisonRepository(CursorRepository):
    def __init__(self) -> None:
        super().__init__()
        self.existing_action = "BUY"
        self.unresolved_events = {
            (
                "BBCA",
                "pluang",
                "instrument-mapping",
                "unrelated_terminal_failure",
            )
        }
        self.resolved_events: set[tuple[str, str, str, str]] = set()
        self.trade_upserts = 0

    async def ingestion_cursor(self, **_: object) -> None:
        return None

    async def has_terminal_quality_block(self, **values: object) -> bool:
        identity = (values["ticker"], values["provider"], values["dataset"])
        return any(event[:3] == identity for event in self.unresolved_events)

    async def record_quality_event(self, **values: object) -> None:
        self.unresolved_events.add(
            (
                str(values["ticker"]),
                str(values["provider"]),
                str(values["dataset"]),
                str(values["reason_code"]),
            )
        )

    async def resolve_quality_event(self, **values: object) -> int:
        identity = (
            str(values["ticker"]),
            str(values["provider"]),
            str(values["dataset"]),
            str(values["reason_code"]),
        )
        if identity not in self.unresolved_events:
            return 0
        self.unresolved_events.remove(identity)
        self.resolved_events.add(identity)
        return 1

    async def broker_flow(self, *_: object) -> list[object]:
        return []

    async def trades_by_sequences(
        self, ticker: str, trade_date: date, sequences: list[str]
    ) -> list[TradePrintRecord]:
        assert ticker == "BBCA"
        assert trade_date == date(2026, 8, 21)
        assert sequences == ["FIXTURE-COMPARISON-001"]
        return [_comparison_trade(self.existing_action)]

    async def latest_orderbook(self, *_: object) -> None:
        return None

    async def upsert_trade_prints(self, _: object) -> tuple[int, int]:
        self.trade_upserts += 1
        return 0, 1


class ComparisonProvider:
    def __init__(self) -> None:
        self.trade_calls = 0

    async def get_broker_summary(self, *_: object) -> tuple[list[object], dict[str, object]]:
        return [], {}

    async def get_running_trades(
        self, *_: object, cursor: str | None = None
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        assert cursor is None
        self.trade_calls += 1
        return RunningTradesPage(records=[_comparison_trade("SELL")], next_cursor=None), {}

    async def get_orderbook(
        self, *_: object
    ) -> tuple[OrderbookSnapshotRecord, dict[str, object]]:
        return (
            OrderbookSnapshotRecord(
                ticker="BBCA",
                observed_at=datetime.fromisoformat("2099-01-01T00:00:00+00:00"),
                best_bid=None,
                best_ask=None,
                spread=None,
                levels=[],
            ),
            {},
        )


def _comparison_trade(action: str) -> TradePrintRecord:
    return TradePrintRecord(
        ticker="BBCA",
        provider_sequence="FIXTURE-COMPARISON-001",
        trade_date=date(2026, 8, 21),
        executed_at=datetime.fromisoformat("2026-08-21T15:49:58+07:00"),
        price=Decimal("6450"),
        lots=1,
        shares=100,
        aggressor_action=action,
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


async def test_successful_recomparison_resolves_only_exact_block_and_reenables_ingestion() -> None:
    repository = ComparisonRepository()
    provider = ComparisonProvider()
    service = PluangIngestionService(provider, repository)  # type: ignore[arg-type]
    comparison_identity = (
        "BBCA",
        "pluang",
        "finance:pluang/running-trades",
        "gateway_source_comparison_mismatch",
    )
    unrelated_identity = (
        "BBCA",
        "pluang",
        "instrument-mapping",
        "unrelated_terminal_failure",
    )

    mismatch = await service.collect_canary(
        ["BBCA"], trade_date=date(2026, 8, 21), max_pages=1, compare_existing=True
    )
    assert mismatch[0].status == "comparison_mismatch"
    assert comparison_identity in repository.unresolved_events

    repository.existing_action = "SELL"
    matched = await service.collect_canary(
        ["BBCA"], trade_date=date(2026, 8, 21), max_pages=1, compare_existing=True
    )
    assert matched[0].status == "succeeded"
    assert comparison_identity in repository.resolved_events
    assert comparison_identity not in repository.unresolved_events
    assert unrelated_identity in repository.unresolved_events
    assert repository.trade_upserts == 0

    calls_before_ordinary_run = provider.trade_calls
    ordinary = await service.collect_canary(
        ["BBCA"], trade_date=date(2026, 8, 21), max_pages=1
    )
    assert ordinary[0].status == "succeeded"
    assert provider.trade_calls == calls_before_ordinary_run + 1
    assert repository.trade_upserts == 1
    assert unrelated_identity in repository.unresolved_events
