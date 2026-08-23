import asyncio
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.schemas.warehouse import (
    BrokerFlowRecord,
    IngestionCursorState,
    MarketPriorityCandidate,
    RunningTradesPage,
    TradebookAggregateRecord,
    TradePrintRecord,
)


class CollectionProvider(Protocol):
    async def get_broker_summary(
        self, ticker: str, trade_date: date
    ) -> tuple[list[BrokerFlowRecord], dict[str, object]]: ...

    async def get_tradebook(
        self, ticker: str, trade_date: date, *, tab: str = "ALL"
    ) -> tuple[list[TradebookAggregateRecord], dict[str, object]]: ...

    async def get_running_trades(
        self,
        ticker: str,
        trade_date: date,
        *,
        cursor: str | None = None,
        min_lot: int | None = None,
        action: str | None = None,
    ) -> tuple[RunningTradesPage, dict[str, object]]: ...


class CollectionRepository(Protocol):
    async def ingestion_cursor(
        self, *, ticker: str, provider: str, dataset: str, session_date: date
    ) -> IngestionCursorState | None: ...

    async def update_cursor(
        self,
        *,
        ticker: str,
        provider: str,
        dataset: str,
        instrument_key: str,
        session_date: date | None,
        cursor_value: str | None,
        high_water_mark: str | None,
        status: str,
        error_message: str | None = None,
        collection_filter: dict[str, object] | None = None,
        collection_floor_idr: Decimal | None = None,
        rows_fetched: int = 0,
        rows_retained: int = 0,
    ) -> None: ...

    async def has_terminal_quality_block(
        self, *, ticker: str, provider: str, dataset: str
    ) -> bool: ...

    async def upsert_broker_flow(
        self, records: list[BrokerFlowRecord]
    ) -> tuple[int, int]: ...

    async def upsert_tradebook(
        self, records: list[TradebookAggregateRecord]
    ) -> tuple[int, int]: ...

    async def upsert_trade_prints(
        self, records: list[TradePrintRecord]
    ) -> tuple[int, int]: ...


@dataclass(frozen=True)
class CollectionResult:
    ticker: str
    dataset: str
    status: str
    requests: int
    rows_fetched: int
    rows_retained: int
    cursor_remaining: bool = False
    error: str | None = None


def calculate_min_lot(min_trade_value_idr: Decimal, reference_price: Decimal) -> int:
    if min_trade_value_idr < 0:
        raise ValueError("min_trade_value_idr must be non-negative")
    if reference_price <= 0:
        raise ValueError("reference_price must be positive")
    return math.ceil(min_trade_value_idr / (reference_price * 100))


def prioritize_market_candidates(
    candidates: Sequence[MarketPriorityCandidate],
    *,
    strategic_watchlist: Sequence[str] = (),
) -> list[MarketPriorityCandidate]:
    strategic_rank = {
        ticker.strip().upper(): index for index, ticker in enumerate(strategic_watchlist)
    }

    def key(candidate: MarketPriorityCandidate) -> tuple[object, ...]:
        market_cap = (
            candidate.latest_close * candidate.listed_shares
            if candidate.latest_close is not None and candidate.listed_shares is not None
            else Decimal("-1")
        )
        return (
            0 if candidate.ticker in strategic_rank else 1,
            strategic_rank.get(candidate.ticker, len(strategic_rank)),
            -market_cap,
            -(candidate.value_idr or Decimal("-1")),
            -(candidate.frequency or -1),
            candidate.ticker,
        )

    return sorted(candidates, key=key)


def select_quota_safe_universe(
    candidates: Sequence[MarketPriorityCandidate],
    *,
    available_requests: int,
    requests_per_ticker: int,
    strategic_watchlist: Sequence[str] = (),
) -> list[MarketPriorityCandidate]:
    if available_requests < 0 or requests_per_ticker < 1:
        raise ValueError("quota inputs must be non-negative and per-ticker cost positive")
    limit = available_requests // requests_per_ticker
    return prioritize_market_candidates(
        candidates, strategic_watchlist=strategic_watchlist
    )[:limit]


def request_economics(
    *, per_ticker_requests: int, universe_sizes: Sequence[int], trading_days: int = 22
) -> dict[int, tuple[int, int]]:
    if per_ticker_requests < 0 or trading_days < 1:
        raise ValueError("request economics inputs are invalid")
    return {
        size: (size * per_ticker_requests, size * per_ticker_requests * trading_days)
        for size in universe_sizes
    }


class MarketCollectionService:
    def __init__(
        self, provider: CollectionProvider, repository: CollectionRepository
    ) -> None:
        self._provider = provider
        self._repository = repository

    async def collect_broker_daily(
        self, tickers: Sequence[str], *, trade_date: date, concurrency: int = 2
    ) -> list[CollectionResult]:
        return await self._collect_single_request_dataset(
            tickers,
            trade_date=trade_date,
            concurrency=concurrency,
            dataset="broker-summary",
        )

    async def collect_tradebook(
        self, tickers: Sequence[str], *, trade_date: date, concurrency: int = 2
    ) -> list[CollectionResult]:
        return await self._collect_single_request_dataset(
            tickers,
            trade_date=trade_date,
            concurrency=concurrency,
            dataset="tradebook",
        )

    async def _collect_single_request_dataset(
        self,
        tickers: Sequence[str],
        *,
        trade_date: date,
        concurrency: int,
        dataset: str,
    ) -> list[CollectionResult]:
        if not 1 <= concurrency <= 10:
            raise ValueError("concurrency must be between 1 and 10")
        unique = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers))
        semaphore = asyncio.Semaphore(concurrency)

        async def collect(ticker: str) -> CollectionResult:
            async with semaphore:
                return await self._collect_single(ticker, trade_date, dataset)

        return list(await asyncio.gather(*(collect(ticker) for ticker in unique)))

    async def _collect_single(
        self, ticker: str, trade_date: date, dataset: str
    ) -> CollectionResult:
        full_dataset = f"finance:pluang/{dataset}"
        if await self._repository.has_terminal_quality_block(
            ticker=ticker, provider="pluang", dataset=full_dataset
        ):
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="blocked",
                error_message="terminal data-quality block",
            )
            return CollectionResult(ticker, dataset, "blocked", 0, 0, 0)
        checkpoint = await self._repository.ingestion_cursor(
            ticker=ticker,
            provider="pluang",
            dataset=dataset,
            session_date=trade_date,
        )
        if checkpoint and checkpoint.status == "complete":
            return CollectionResult(
                ticker,
                dataset,
                "skipped",
                0,
                checkpoint.rows_fetched,
                checkpoint.rows_retained,
            )
        try:
            await self._set_cursor(ticker, dataset, trade_date, status="running")
            if dataset == "broker-summary":
                broker_rows, _ = await self._provider.get_broker_summary(
                    ticker, trade_date
                )
                await self._repository.upsert_broker_flow(broker_rows)
                count = len(broker_rows)
            else:
                tradebook_rows, _ = await self._provider.get_tradebook(
                    ticker, trade_date, tab="ALL"
                )
                await self._repository.upsert_tradebook(tradebook_rows)
                count = len(tradebook_rows)
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="complete",
                rows_fetched=count,
                rows_retained=count,
            )
            return CollectionResult(ticker, dataset, "complete", 1, count, count)
        except Exception as error:
            message = str(error)[:500]
            await self._set_cursor(
                ticker, dataset, trade_date, status="failed", error_message=message
            )
            return CollectionResult(ticker, dataset, "failed", 1, 0, 0, error=message)

    async def collect_running_trades(
        self,
        tickers: Sequence[str],
        *,
        trade_date: date,
        reference_prices: Mapping[str, Decimal],
        min_trade_value_idr: Decimal,
        action: str | None = None,
        max_pages: int = 3,
        concurrency: int = 2,
    ) -> list[CollectionResult]:
        if not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if not 1 <= concurrency <= 10:
            raise ValueError("concurrency must be between 1 and 10")
        if action is not None and action.upper() not in {"BUY", "SELL"}:
            raise ValueError("action must be BUY or SELL")
        unique = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers))
        semaphore = asyncio.Semaphore(concurrency)

        async def collect(ticker: str) -> CollectionResult:
            async with semaphore:
                price = reference_prices.get(ticker)
                if price is None:
                    await self._set_cursor(
                        ticker,
                        "running-trades",
                        trade_date,
                        status="blocked",
                        collection_floor_idr=min_trade_value_idr,
                        error_message="validated reference price is unavailable",
                    )
                    return CollectionResult(
                        ticker,
                        "running-trades",
                        "blocked",
                        0,
                        0,
                        0,
                        error="validated reference price is unavailable",
                    )
                return await self._collect_running_symbol(
                    ticker,
                    trade_date,
                    price,
                    min_trade_value_idr,
                    action,
                    max_pages,
                )

        return list(await asyncio.gather(*(collect(ticker) for ticker in unique)))

    async def _collect_running_symbol(
        self,
        ticker: str,
        trade_date: date,
        reference_price: Decimal,
        min_trade_value_idr: Decimal,
        action: str | None,
        max_pages: int,
    ) -> CollectionResult:
        dataset = "running-trades"
        min_lot = calculate_min_lot(min_trade_value_idr, reference_price)
        normalized_action = action.upper() if action else None
        collection_filter: dict[str, object] = {
            "minTradeValueIdr": str(min_trade_value_idr),
            "referencePrice": str(reference_price),
        }
        if min_lot:
            collection_filter["minLot"] = min_lot
        if normalized_action:
            collection_filter["action"] = normalized_action
        if await self._repository.has_terminal_quality_block(
            ticker=ticker,
            provider="pluang",
            dataset="finance:pluang/running-trades",
        ):
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="blocked",
                collection_filter=collection_filter,
                collection_floor_idr=min_trade_value_idr,
                error_message="terminal data-quality block",
            )
            return CollectionResult(ticker, dataset, "blocked", 0, 0, 0)
        checkpoint = await self._repository.ingestion_cursor(
            ticker=ticker,
            provider="pluang",
            dataset=dataset,
            session_date=trade_date,
        )
        if checkpoint and checkpoint.collection_filter != collection_filter:
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="blocked",
                cursor_value=checkpoint.cursor_value,
                high_water_mark=checkpoint.high_water_mark,
                collection_filter=checkpoint.collection_filter,
                collection_floor_idr=checkpoint.collection_floor_idr,
                rows_fetched=checkpoint.rows_fetched,
                rows_retained=checkpoint.rows_retained,
                error_message="collection filter differs from resumable session",
            )
            return CollectionResult(
                ticker,
                dataset,
                "blocked",
                0,
                checkpoint.rows_fetched,
                checkpoint.rows_retained,
                cursor_remaining=bool(checkpoint.cursor_value),
                error="collection filter differs from resumable session",
            )
        if checkpoint and checkpoint.status == "complete":
            return CollectionResult(
                ticker,
                dataset,
                "skipped",
                0,
                checkpoint.rows_fetched,
                checkpoint.rows_retained,
            )
        cursor = checkpoint.cursor_value if checkpoint else None
        high_water = checkpoint.high_water_mark if checkpoint else None
        fetched = checkpoint.rows_fetched if checkpoint else 0
        retained = checkpoint.rows_retained if checkpoint else 0
        requests = 0
        try:
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="running",
                cursor_value=cursor,
                high_water_mark=high_water,
                collection_filter=collection_filter,
                collection_floor_idr=min_trade_value_idr,
                rows_fetched=fetched,
                rows_retained=retained,
            )
            for _ in range(max_pages):
                page, _ = await self._provider.get_running_trades(
                    ticker,
                    trade_date,
                    cursor=cursor,
                    min_lot=min_lot or None,
                    action=normalized_action,
                )
                requests += 1
                fetched += len(page.records)
                deduplicated = {
                    record.provider_sequence: record for record in page.records
                }
                accepted = list(deduplicated.values())
                await self._repository.upsert_trade_prints(accepted)
                retained += len(accepted)
                if accepted:
                    high_water = accepted[-1].provider_sequence
                cursor = page.next_cursor
                status = "complete" if cursor is None else "running"
                await self._set_cursor(
                    ticker,
                    dataset,
                    trade_date,
                    status=status,
                    cursor_value=cursor,
                    high_water_mark=high_water,
                    collection_filter=collection_filter,
                    collection_floor_idr=min_trade_value_idr,
                    rows_fetched=fetched,
                    rows_retained=retained,
                )
                if cursor is None or not page.records:
                    break
            status = "complete" if cursor is None else "partial"
            if cursor is not None:
                await self._set_cursor(
                    ticker,
                    dataset,
                    trade_date,
                    status="partial",
                    cursor_value=cursor,
                    high_water_mark=high_water,
                    collection_filter=collection_filter,
                    collection_floor_idr=min_trade_value_idr,
                    rows_fetched=fetched,
                    rows_retained=retained,
                )
            return CollectionResult(
                ticker,
                dataset,
                status,
                requests,
                fetched,
                retained,
                cursor_remaining=bool(cursor),
            )
        except Exception as error:
            message = str(error)[:500]
            await self._set_cursor(
                ticker,
                dataset,
                trade_date,
                status="failed",
                cursor_value=cursor,
                high_water_mark=high_water,
                collection_filter=collection_filter,
                collection_floor_idr=min_trade_value_idr,
                rows_fetched=fetched,
                rows_retained=retained,
                error_message=message,
            )
            return CollectionResult(
                ticker,
                dataset,
                "failed",
                requests,
                fetched,
                retained,
                cursor_remaining=bool(cursor),
                error=message,
            )

    async def _set_cursor(
        self,
        ticker: str,
        dataset: str,
        trade_date: date,
        *,
        status: str,
        cursor_value: str | None = None,
        high_water_mark: str | None = None,
        collection_filter: dict[str, object] | None = None,
        collection_floor_idr: Decimal | None = None,
        rows_fetched: int = 0,
        rows_retained: int = 0,
        error_message: str | None = None,
    ) -> None:
        await self._repository.update_cursor(
            ticker=ticker,
            provider="pluang",
            dataset=dataset,
            instrument_key=ticker,
            session_date=trade_date,
            cursor_value=cursor_value,
            high_water_mark=high_water_mark,
            status=status,
            error_message=error_message,
            collection_filter=collection_filter or {},
            collection_floor_idr=collection_floor_idr,
            rows_fetched=rows_fetched,
            rows_retained=rows_retained,
        )
