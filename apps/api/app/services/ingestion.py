import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

import httpx

from app.providers.base import MarketDataProvider
from app.repositories.base import MarketRepository


class IngestionService:
    def __init__(self, provider: MarketDataProvider, repository: MarketRepository):
        self._provider = provider
        self._repository = repository

    async def ingest_ticker(
        self,
        ticker: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 260,
    ) -> tuple[int, int]:
        run_id = await self._repository.start_ingestion(self._provider.name, date_to)
        try:
            history = await self._provider.get_stock_history(
                ticker, date_from=date_from, date_to=date_to, limit=limit
            )
            inserted, updated = await self._repository.upsert_history(history.stock, history.bars)
            await self._repository.finish_ingestion(
                run_id,
                status="succeeded",
                rows_received=len(history.bars),
                rows_inserted=inserted,
                rows_updated=updated,
            )
            return inserted, updated
        except Exception as error:
            await self._repository.finish_ingestion(
                run_id,
                status="failed",
                rows_received=0,
                rows_inserted=0,
                rows_updated=0,
                error_message=str(error),
            )
            raise


class IngestionMode(StrEnum):
    AUTO = "auto"
    BACKFILL = "backfill"
    INCREMENTAL = "incremental"


@dataclass(frozen=True)
class TickerIngestionResult:
    ticker: str
    status: str
    mode: IngestionMode
    rows_received: int
    rows_inserted: int
    rows_updated: int
    rows_rejected: int = 0
    error: str | None = None


@dataclass(frozen=True)
class UniverseSyncResult:
    discovered: int
    inserted: int
    updated: int
    deactivated: int


@dataclass(frozen=True)
class BatchIngestionResult:
    results: list[TickerIngestionResult]

    @property
    def completed(self) -> int:
        return sum(result.status == "succeeded" for result in self.results)

    @property
    def failed(self) -> int:
        return sum(result.status == "failed" for result in self.results)


class EodBatchIngestionService:
    dataset = "stock-history"

    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketRepository,
        *,
        failure_recorder: Callable[[str, str, bool, bool], Awaitable[None]] | None = None,
    ):
        self._provider = provider
        self._repository = repository
        self._failure_recorder = failure_recorder

    async def synchronize_universe(self) -> UniverseSyncResult:
        universe = await self._provider.get_stock_universe()
        if len(universe.stocks) != universe.total:
            raise ValueError("provider universe is incomplete")
        inserted, updated, deactivated = await self._repository.sync_stock_universe(
            universe.stocks, deactivate_missing=True
        )
        return UniverseSyncResult(universe.total, inserted, updated, deactivated)

    async def failed_tickers(self) -> list[str]:
        return await self._repository.checkpoint_tickers(
            provider=self._provider.name,
            dataset=self.dataset,
            status="failed",
        )

    async def resumable_tickers(self, *, include_terminal: bool = False) -> list[str]:
        return await self._repository.resumable_tickers(
            provider=self._provider.name,
            dataset=self.dataset,
            include_terminal=include_terminal,
        )

    async def ingest(
        self,
        tickers: list[str],
        *,
        mode: IngestionMode = IngestionMode.AUTO,
        target_sessions: int = 260,
        revision_days: int = 14,
        concurrency: int = 2,
    ) -> BatchIngestionResult:
        normalized = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers))
        if not normalized:
            return BatchIngestionResult([])
        if not 1 <= concurrency <= 10:
            raise ValueError("concurrency must be between 1 and 10")
        if target_sessions < 1:
            raise ValueError("target_sessions must be positive")
        if revision_days < 1:
            raise ValueError("revision_days must be positive")

        run_id = await self._repository.start_ingestion(self._provider.name, None)
        semaphore = asyncio.Semaphore(concurrency)

        async def ingest_one(ticker: str) -> TickerIngestionResult:
            async with semaphore:
                return await self._ingest_one(
                    ticker,
                    mode=mode,
                    target_sessions=target_sessions,
                    revision_days=revision_days,
                )

        results = list(await asyncio.gather(*(ingest_one(ticker) for ticker in normalized)))
        received = sum(result.rows_received for result in results)
        inserted = sum(result.rows_inserted for result in results)
        updated = sum(result.rows_updated for result in results)
        failures = [result for result in results if result.status == "failed"]
        await self._repository.finish_ingestion(
            run_id,
            status="failed" if failures else "succeeded",
            rows_received=received,
            rows_inserted=inserted,
            rows_updated=updated,
            error_message=(
                "; ".join(f"{result.ticker}: {result.error}" for result in failures)
                if failures
                else None
            ),
        )
        return BatchIngestionResult(results)

    async def _ingest_one(
        self,
        ticker: str,
        *,
        mode: IngestionMode,
        target_sessions: int,
        revision_days: int,
    ) -> TickerIngestionResult:
        effective_mode = mode
        try:
            state = await self._repository.history_state(ticker)
            if mode is IngestionMode.AUTO:
                minimum_complete_rows = max(1, int(target_sessions * 0.9))
                effective_mode = (
                    IngestionMode.INCREMENTAL
                    if state.row_count >= minimum_complete_rows
                    and state.latest_trade_date is not None
                    else IngestionMode.BACKFILL
                )
            date_from = None
            if effective_mode is IngestionMode.INCREMENTAL and state.latest_trade_date:
                date_from = state.latest_trade_date - timedelta(days=revision_days)

            await self._repository.update_checkpoint(
                ticker,
                provider=self._provider.name,
                dataset=self.dataset,
                status="running",
            )
            history = await self._provider.get_stock_history(
                ticker,
                date_from=date_from,
                limit=target_sessions,
            )
            if not history.bars:
                raise ValueError("empty_history: provider returned no valid market bars")
            inserted, updated = await self._repository.upsert_history(history.stock, history.bars)
            latest = max(
                (bar.trade_date for bar in history.bars),
                default=state.latest_trade_date,
            )
            await self._repository.update_checkpoint(
                ticker,
                provider=self._provider.name,
                dataset=self.dataset,
                status="succeeded",
                last_successful_trade_date=latest,
                error_message=(
                    f"rejected {history.rejected_items} invalid provider rows"
                    if history.rejected_items
                    else None
                ),
            )
            return TickerIngestionResult(
                ticker,
                "succeeded",
                effective_mode,
                len(history.bars),
                inserted,
                updated,
                history.rejected_items,
            )
        except Exception as error:
            message = str(error)[:1000]
            reason, retryable, terminal = _classify_eod_error(error)
            if self._failure_recorder:
                with suppress(LookupError, RuntimeError):
                    await self._failure_recorder(ticker, reason, retryable, terminal)
            with suppress(LookupError, RuntimeError):
                await self._repository.update_checkpoint(
                    ticker,
                    provider=self._provider.name,
                    dataset=self.dataset,
                    status="failed",
                    error_message=message,
                )
            return TickerIngestionResult(ticker, "failed", effective_mode, 0, 0, 0, 0, message)


def _classify_eod_error(error: Exception) -> tuple[str, bool, bool]:
    message = str(error).lower()
    if isinstance(error, httpx.HTTPStatusError):
        retryable = error.response.status_code == 429 or error.response.status_code >= 500
        return f"provider_http_{error.response.status_code}", retryable, not retryable
    if isinstance(error, httpx.RequestError):
        return "provider_transient", True, False
    if "empty_history" in message or "no valid market bars" in message:
        return "empty_history", False, True
    if "unit must be shares" in message:
        return "malformed_unit", False, True
    if "stock-history" in message or isinstance(error, ValueError):
        return "validation_failure", False, True
    return "provider_failure", True, False


async def seed_mock_repository(provider: MarketDataProvider, repository: MarketRepository) -> None:
    summary = await provider.get_daily_market_summary()
    rows_received = 0
    for item in summary:
        history = await provider.get_stock_history(item.stock.ticker, limit=260)
        rows_received += len(history.bars)
        await repository.upsert_history(history.stock, history.bars)
    run_id = await repository.start_ingestion(provider.name, None)
    await repository.finish_ingestion(
        run_id,
        status="succeeded",
        rows_received=rows_received,
        rows_inserted=0,
        rows_updated=0,
    )
