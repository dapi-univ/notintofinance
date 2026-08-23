from datetime import date, datetime
from decimal import Decimal

from app.schemas.warehouse import (
    BrokerFlowRecord,
    IngestionCursorState,
    MarketPriorityCandidate,
    RunningTradesPage,
    TradebookAggregateRecord,
    TradePrintRecord,
)
from app.services.collection import (
    MarketCollectionService,
    calculate_min_lot,
    prioritize_market_candidates,
    request_economics,
    select_quota_safe_universe,
)


class CollectionRepository:
    def __init__(self) -> None:
        self.cursors: dict[tuple[str, str, date], IngestionCursorState] = {}
        self.broker_identities: set[tuple[object, ...]] = set()
        self.trade_identities: set[str] = set()
        self.tradebook_identities: set[tuple[str, str]] = set()

    async def ingestion_cursor(self, **values: object) -> IngestionCursorState | None:
        return self.cursors.get(
            (str(values["ticker"]), str(values["dataset"]), values["session_date"])  # type: ignore[arg-type]
        )

    async def update_cursor(self, **values: object) -> None:
        key = (
            str(values["ticker"]),
            str(values["dataset"]),
            values["session_date"],  # type: ignore[arg-type]
        )
        self.cursors[key] = IngestionCursorState(
            instrument_key=str(values["instrument_key"]),
            session_date=values["session_date"],  # type: ignore[arg-type]
            cursor_value=values.get("cursor_value"),  # type: ignore[arg-type]
            high_water_mark=values.get("high_water_mark"),  # type: ignore[arg-type]
            status=str(values["status"]),
            collection_filter=values.get("collection_filter", {}),  # type: ignore[arg-type]
            collection_floor_idr=values.get("collection_floor_idr"),  # type: ignore[arg-type]
            rows_fetched=int(values.get("rows_fetched", 0)),
            rows_retained=int(values.get("rows_retained", 0)),
        )

    async def has_terminal_quality_block(self, **_: object) -> bool:
        return False

    async def upsert_broker_flow(
        self, records: list[BrokerFlowRecord]
    ) -> tuple[int, int]:
        before = len(self.broker_identities)
        self.broker_identities.update(
            (row.ticker, row.trade_date_to, row.side, row.broker_code) for row in records
        )
        inserted = len(self.broker_identities) - before
        return inserted, len(records) - inserted

    async def upsert_tradebook(
        self, records: list[TradebookAggregateRecord]
    ) -> tuple[int, int]:
        before = len(self.tradebook_identities)
        self.tradebook_identities.update(
            (row.view_type, row.bucket_key) for row in records
        )
        inserted = len(self.tradebook_identities) - before
        return inserted, len(records) - inserted

    async def upsert_trade_prints(
        self, records: list[TradePrintRecord]
    ) -> tuple[int, int]:
        before = len(self.trade_identities)
        self.trade_identities.update(row.provider_sequence for row in records)
        inserted = len(self.trade_identities) - before
        return inserted, len(records) - inserted


class CollectionProvider:
    def __init__(self) -> None:
        self.broker_calls: list[str] = []
        self.running_calls: list[dict[str, object]] = []

    async def get_broker_summary(
        self, ticker: str, trade_date: date
    ) -> tuple[list[BrokerFlowRecord], dict[str, object]]:
        self.broker_calls.append(ticker)
        return [
            BrokerFlowRecord(
                ticker=ticker,
                trade_date_from=trade_date,
                trade_date_to=trade_date,
                broker_code="AK",
                side="BUY",
                rank=1,
                lots=10,
                shares=1000,
                value_idr=Decimal("6450000"),
                average_price=Decimal("6450"),
                source_scope="top_n",
                source_top_n=10,
            )
        ], {}

    async def get_tradebook(
        self, *_: object, **__: object
    ) -> tuple[list[TradebookAggregateRecord], dict[str, object]]:
        return [], {}

    async def get_running_trades(
        self,
        ticker: str,
        trade_date: date,
        *,
        cursor: str | None = None,
        min_lot: int | None = None,
        action: str | None = None,
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        self.running_calls.append(
            {"ticker": ticker, "cursor": cursor, "min_lot": min_lot, "action": action}
        )
        sequence = "PAGE-1" if cursor is None else "PAGE-2"
        return RunningTradesPage(
            records=[
                TradePrintRecord(
                    ticker=ticker,
                    provider_sequence=sequence,
                    trade_date=trade_date,
                    executed_at=datetime.fromisoformat(
                        f"{trade_date.isoformat()}T10:00:00+07:00"
                    ),
                    price=Decimal("6450"),
                    lots=min_lot or 1,
                    shares=(min_lot or 1) * 100,
                    aggressor_action=action or "BUY",
                )
            ],
            next_cursor="opaque-next" if cursor is None else None,
        ), {}


def _candidate(
    ticker: str, close: str, shares: int, value: str, frequency: int
) -> MarketPriorityCandidate:
    return MarketPriorityCandidate(
        ticker=ticker,
        latest_close=Decimal(close),
        listed_shares=shares,
        value_idr=Decimal(value),
        frequency=frequency,
    )


def test_collection_floor_uses_reference_price_and_board_lot() -> None:
    assert calculate_min_lot(Decimal("0"), Decimal("6450")) == 0
    assert calculate_min_lot(Decimal("10000000"), Decimal("6450")) == 16
    assert calculate_min_lot(Decimal("10000000"), Decimal("3170")) == 32


def test_priority_is_stable_significance_based_and_never_input_order_based() -> None:
    candidates = [
        _candidate("SMALL", "100", 1_000, "1000", 2),
        _candidate("LARGE", "100", 1_000_000, "900", 1),
        _candidate("MEDIUM", "100", 100_000, "5000", 5),
    ]

    first = prioritize_market_candidates(candidates)
    second = prioritize_market_candidates(list(reversed(candidates)))
    strategic = prioritize_market_candidates(candidates, strategic_watchlist=["SMALL"])

    assert [item.ticker for item in first] == ["LARGE", "MEDIUM", "SMALL"]
    assert [item.ticker for item in second] == ["LARGE", "MEDIUM", "SMALL"]
    assert strategic[0].ticker == "SMALL"


def test_quota_ramp_down_takes_a_deterministic_priority_prefix() -> None:
    candidates = [
        _candidate("A", "1", 100, "100", 1),
        _candidate("B", "1", 300, "300", 3),
        _candidate("C", "1", 200, "200", 2),
    ]

    selected = select_quota_safe_universe(
        candidates, available_requests=4, requests_per_ticker=2
    )

    assert [item.ticker for item in selected] == ["B", "C"]
    assert request_economics(per_ticker_requests=1, universe_sizes=[50])[50] == (
        50,
        1100,
    )


async def test_full_candidate_broker_collection_is_idempotent() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]
    session = date(2026, 8, 21)

    first = await service.collect_broker_daily(
        ["BBCA", "AADI"], trade_date=session, concurrency=2
    )
    second = await service.collect_broker_daily(
        ["BBCA", "AADI"], trade_date=session, concurrency=2
    )

    assert [item.status for item in first] == ["complete", "complete"]
    assert [item.status for item in second] == ["skipped", "skipped"]
    assert sorted(provider.broker_calls) == ["AADI", "BBCA"]
    assert len(repository.broker_identities) == 2


async def test_running_cursor_is_partial_then_resumes_to_complete_with_same_filter() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]
    kwargs = {
        "trade_date": date(2026, 8, 21),
        "reference_prices": {"BBCA": Decimal("6450")},
        "min_trade_value_idr": Decimal("10000000"),
        "action": "SELL",
        "max_pages": 1,
        "concurrency": 1,
    }

    partial = await service.collect_running_trades(["BBCA"], **kwargs)  # type: ignore[arg-type]
    complete = await service.collect_running_trades(["BBCA"], **kwargs)  # type: ignore[arg-type]
    state = repository.cursors[("BBCA", "running-trades", date(2026, 8, 21))]

    assert partial[0].status == "partial"
    assert partial[0].cursor_remaining
    assert complete[0].status == "complete"
    assert not complete[0].cursor_remaining
    assert state.status == "complete"
    assert state.rows_fetched == state.rows_retained == 2
    assert state.collection_filter["minLot"] == 16
    assert provider.running_calls == [
        {"ticker": "BBCA", "cursor": None, "min_lot": 16, "action": "SELL"},
        {
            "ticker": "BBCA",
            "cursor": "opaque-next",
            "min_lot": 16,
            "action": "SELL",
        },
    ]


async def test_resumable_session_rejects_a_different_collection_floor() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]
    session = date(2026, 8, 21)
    await service.collect_running_trades(
        ["BBCA"],
        trade_date=session,
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal("10000000"),
        max_pages=1,
        concurrency=1,
    )

    blocked = await service.collect_running_trades(
        ["BBCA"],
        trade_date=session,
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal("5000000"),
        max_pages=1,
        concurrency=1,
    )

    assert blocked[0].status == "blocked"
    assert len(provider.running_calls) == 1
