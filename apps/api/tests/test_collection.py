from datetime import UTC, date, datetime
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
        self.latest_session = date(2026, 8, 21)
        self.tradebook_sessions: list[object] = []
        self.upserted_trades: list[TradePrintRecord] = []

    async def latest_market_session(self) -> date | None:
        return self.latest_session

    async def ticker_has_eod(self, ticker: str, trade_date: date) -> bool:
        del ticker
        return trade_date == self.latest_session

    async def upsert_tradebook_session(self, record: object) -> None:
        self.tradebook_sessions.append(record)

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
        self.upserted_trades.extend(records)
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
        ], {
            "data": {
                "startDate": trade_date.isoformat(),
                "endDate": trade_date.isoformat(),
            }
        }

    async def get_tradebook(
        self, ticker: str, *_: object, **__: object
    ) -> tuple[list[TradebookAggregateRecord], dict[str, object]]:
        return [], {
            "data": {
                "code": ticker,
                "source": "pluang",
                "byPrice": [{"price": 1}],
                "byTime": [{"time": "09:00:00"}],
                "byVolume": [],
            },
            "timestamp": "2026-08-21T09:30:00Z",
        }

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
        ), {"timestamp": "2026-08-21T09:30:00Z"}


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


async def test_broker_summary_rejects_silent_historical_date_substitution() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]
    original = provider.get_broker_summary

    async def wrong_date(
        ticker: str, trade_date: date
    ) -> tuple[list[BrokerFlowRecord], dict[str, object]]:
        rows, payload = await original(ticker, trade_date)
        body = payload["data"]
        assert isinstance(body, dict)
        body["endDate"] = "2026-08-20"
        return rows, payload

    provider.get_broker_summary = wrong_date  # type: ignore[method-assign]

    result = await service.collect_broker_daily(
        ["BBCA"], trade_date=date(2026, 8, 21), concurrency=1
    )

    assert result[0].status == "failed"
    assert "does not match" in (result[0].error or "")
    assert repository.broker_identities == set()


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
    assert state.high_water_mark == "PAGE-1"
    assert complete[0].coverage_scope == "filtered"
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


async def test_ephemeral_collection_rejects_non_latest_and_active_unconfirmed_day() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    historical = MarketCollectionService(
        provider,
        repository,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 8, 23, 2, tzinfo=UTC),
    )
    active_day = MarketCollectionService(
        provider,
        repository,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 8, 24, 2, tzinfo=UTC),
    )

    old = await historical.collect_tradebook(
        ["BBCA"], trade_date=date(2026, 8, 20), concurrency=1
    )
    unconfirmed = await active_day.collect_running_trades(
        ["BBCA"],
        trade_date=date(2026, 8, 21),
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal(0),
        concurrency=1,
    )

    assert old[0].status == "blocked"
    assert "latest confirmed" in (old[0].error or "")
    assert unconfirmed[0].status == "blocked"
    assert "newer market day" in (unconfirmed[0].error or "")
    assert provider.running_calls == []


async def test_weekend_latest_session_binds_unasserted_provider_observation() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(
        provider,
        repository,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 8, 23, 2, tzinfo=UTC),
    )

    result = await service.collect_running_trades(
        ["BBCA"],
        trade_date=date(2026, 8, 21),
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal(0),
        max_pages=2,
        concurrency=1,
    )

    assert result[0].status == "complete"
    assert result[0].coverage_scope == "unfiltered"
    assert repository.upserted_trades
    assert all(
        row.session_binding_method == "confirmed_latest_eod"
        and row.provider_session_asserted is False
        and row.gateway_observed_at is not None
        for row in repository.upserted_trades
    )


async def test_tradebook_records_component_availability_without_fabricating_volume() -> None:
    provider = CollectionProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]

    result = await service.collect_tradebook(
        ["BBCA"], trade_date=date(2026, 8, 21), concurrency=1
    )

    session = repository.tradebook_sessions[0]
    assert result[0].status == "complete"
    assert session.price_available is True  # type: ignore[attr-defined]
    assert session.time_available is True  # type: ignore[attr-defined]
    assert session.volume_available is False  # type: ignore[attr-defined]
    assert session.provider_session_asserted is False  # type: ignore[attr-defined]


class OverlapProvider(CollectionProvider):
    async def get_running_trades(
        self,
        ticker: str,
        trade_date: date,
        *,
        cursor: str | None = None,
        min_lot: int | None = None,
        action: str | None = None,
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        del min_lot, action
        sequences = ["200", "199"] if cursor is None else ["199", "198"]
        records = [
            TradePrintRecord(
                ticker=ticker,
                provider_sequence=sequence,
                trade_date=trade_date,
                executed_at=datetime.fromisoformat(
                    f"{trade_date.isoformat()}T10:00:00+07:00"
                ),
                price=Decimal("6450"),
                lots=1,
                shares=100,
                aggressor_action="BUY",
            )
            for sequence in sequences
        ]
        return RunningTradesPage(
            records=records, next_cursor="older" if cursor is None else None
        ), {"timestamp": "2026-08-21T09:30:00Z"}


async def test_running_newest_head_overlap_and_retry_counters_are_truthful() -> None:
    provider = OverlapProvider()
    repository = CollectionRepository()
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]

    result = await service.collect_running_trades(
        ["BBCA"],
        trade_date=date(2026, 8, 21),
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal(0),
        max_pages=2,
        concurrency=1,
    )
    state = repository.cursors[("BBCA", "running-trades", date(2026, 8, 21))]

    assert result[0].rows_fetched == 4
    assert result[0].rows_retained == 3
    assert state.high_water_mark == "200"
    assert state.status == "complete"


async def test_legacy_partial_cursor_preserves_original_head() -> None:
    provider = OverlapProvider()
    repository = CollectionRepository()
    repository.trade_identities.update({"200", "199"})
    repository.cursors[("BBCA", "running-trades", date(2026, 8, 21))] = (
        IngestionCursorState(
            instrument_key="BBCA",
            session_date=date(2026, 8, 21),
            cursor_value="legacy-older",
            high_water_mark="17839",
            status="partial",
            collection_filter={
                "minTradeValueIdr": "0",
                "referencePrice": "6450",
            },
            collection_floor_idr=Decimal(0),
        )
    )
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]

    result = await service.collect_running_trades(
        ["BBCA"],
        trade_date=date(2026, 8, 21),
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal(0),
        max_pages=1,
        concurrency=1,
    )
    state = repository.cursors[("BBCA", "running-trades", date(2026, 8, 21))]

    assert result[0].rows_retained == 1
    assert state.high_water_mark == "17839"


async def test_all_updated_repeated_page_retains_zero_unique_facts() -> None:
    provider = OverlapProvider()
    repository = CollectionRepository()
    repository.trade_identities.update({"200", "199"})
    service = MarketCollectionService(provider, repository)  # type: ignore[arg-type]

    result = await service.collect_running_trades(
        ["BBCA"],
        trade_date=date(2026, 8, 21),
        reference_prices={"BBCA": Decimal("6450")},
        min_trade_value_idr=Decimal(0),
        max_pages=1,
        concurrency=1,
    )

    assert result[0].status == "partial"
    assert result[0].rows_fetched == 2
    assert result[0].rows_retained == 0
