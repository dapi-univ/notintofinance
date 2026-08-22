from datetime import date

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
