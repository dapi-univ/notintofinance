from datetime import date

from app.providers.mock import MockMarketDataProvider
from app.repositories.memory import MemoryMarketRepository
from app.schemas.domain import ProviderHistory, ProviderUniverse
from app.services.ingestion import EodBatchIngestionService, IngestionMode
from app.services.market import HistoryTimeframe, MarketService


class RecordingProvider:
    name = "recording"

    def __init__(self, *, fail: set[str] | None = None) -> None:
        self._delegate = MockMarketDataProvider()
        self.fail = fail or set()
        self.history_calls: list[tuple[str, date | None, int]] = []

    async def get_stock_universe(self) -> ProviderUniverse:
        return await self._delegate.get_stock_universe()

    async def get_stock_history(
        self,
        ticker: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 260,
    ) -> ProviderHistory:
        self.history_calls.append((ticker, date_from, limit))
        if ticker in self.fail:
            raise RuntimeError("provider unavailable")
        return await self._delegate.get_stock_history(
            ticker, date_from=date_from, date_to=date_to, limit=limit
        )

    async def get_daily_market_summary(
        self, *, trade_date: date | None = None
    ) -> list[ProviderHistory]:
        return await self._delegate.get_daily_market_summary(trade_date=trade_date)


async def test_universe_sync_is_idempotent_and_deactivates_missing_stocks() -> None:
    repository = MemoryMarketRepository()
    provider = RecordingProvider()
    service = EodBatchIngestionService(provider, repository)

    first = await service.synchronize_universe()
    second = await service.synchronize_universe()
    full_universe = await provider.get_stock_universe()
    _inserted, _updated, deactivated = await repository.sync_stock_universe(
        full_universe.stocks[:-1], deactivate_missing=True
    )

    assert first.inserted == first.discovered == 6
    assert second.inserted == 0
    assert second.updated == 6
    assert deactivated == 1
    assert len(await repository.list_stocks()) == 5


async def test_backfill_upsert_and_idempotent_second_execution() -> None:
    repository = MemoryMarketRepository()
    provider = RecordingProvider()
    service = EodBatchIngestionService(provider, repository)
    await service.synchronize_universe()

    first = await service.ingest(["BMRI"], mode=IngestionMode.BACKFILL)
    second = await service.ingest(["BMRI"], mode=IngestionMode.BACKFILL)

    assert first.results[0].rows_inserted == 260
    assert second.results[0].rows_inserted == 0
    assert second.results[0].rows_updated == 260


async def test_auto_mode_refreshes_only_the_recent_window_after_backfill() -> None:
    repository = MemoryMarketRepository()
    provider = RecordingProvider()
    service = EodBatchIngestionService(provider, repository)
    await service.synchronize_universe()
    await service.ingest(["BBCA"], mode=IngestionMode.AUTO)

    second = await service.ingest(["BBCA"], mode=IngestionMode.AUTO, revision_days=14)

    assert second.results[0].mode is IngestionMode.INCREMENTAL
    assert provider.history_calls[-1][1] == date(2026, 8, 7)
    assert 0 < second.results[0].rows_updated < 260


async def test_partial_failure_is_isolated_and_checkpoint_is_resumable() -> None:
    repository = MemoryMarketRepository()
    provider = RecordingProvider(fail={"ANTM"})
    service = EodBatchIngestionService(provider, repository)
    await service.synchronize_universe()

    result = await service.ingest(["BBCA", "ANTM"], concurrency=2)

    assert result.completed == 1
    assert result.failed == 1
    assert await service.failed_tickers() == ["ANTM"]
    resumable = await service.resumable_tickers()
    assert "ANTM" in resumable
    assert "BBCA" not in resumable
    assert "TLKM" in resumable
    assert (
        len(await repository.get_history("BBCA", date_from=None, date_to=None, limit=None)) == 260
    )


async def test_provider_outage_does_not_prevent_database_history_reads() -> None:
    repository = MemoryMarketRepository()
    healthy_provider = RecordingProvider()
    ingestion = EodBatchIngestionService(healthy_provider, repository)
    await ingestion.synchronize_universe()
    await ingestion.ingest(["BBCA"])
    market = MarketService(repository, provider="zapi", is_mock=False)

    failing_provider = RecordingProvider(fail={"BBCA"})
    failed_ingestion = EodBatchIngestionService(failing_provider, repository)
    assert (await failed_ingestion.ingest(["BBCA"])).failed == 1
    history = await market.get_history(
        "BBCA",
        date_from=None,
        date_to=None,
        limit=None,
        timeframe=HistoryTimeframe.ALL,
        as_of=date(2026, 8, 23),
    )

    assert history is not None
    assert len(history.bars) == 260
    assert history.bars[-1].frequency_analyzer_raw_shares is not None
