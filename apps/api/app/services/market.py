from datetime import date, timedelta
from decimal import Decimal

from app.analytics.frequency_analyzer import frequency_analyzer_raw
from app.repositories.base import MarketRepository
from app.schemas.api import (
    DataStatusResponse,
    HistoryBarResponse,
    HistoryResponse,
    IngestionStatusResponse,
    StockDetailResponse,
    StockListItemResponse,
)


def expected_latest_trade_date(as_of: date) -> date:
    cursor = as_of
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


class MarketService:
    def __init__(self, repository: MarketRepository, *, provider: str, is_mock: bool):
        self._repository = repository
        self._provider = provider
        self._is_mock = is_mock

    async def list_stocks(self) -> list[StockListItemResponse]:
        snapshots = await self._repository.list_stocks()
        return [
            StockListItemResponse(
                ticker=item.stock.ticker,
                company_name=item.stock.company_name,
                sector=item.stock.sector,
                latest_close=item.latest_close,
                change=(item.latest_close - item.previous)
                if item.latest_close is not None and item.previous is not None
                else None,
                change_percent=(
                    ((item.latest_close - item.previous) / item.previous) * 100
                    if item.latest_close is not None
                    and item.previous is not None
                    and item.previous != 0
                    else None
                ),
                latest_trade_date=item.latest_trade_date,
                sparkline=item.sparkline,
            )
            for item in snapshots
        ]

    async def get_stock(self, ticker: str) -> StockDetailResponse | None:
        stock = await self._repository.get_stock(ticker)
        return StockDetailResponse(**stock.model_dump()) if stock else None

    async def get_history(
        self,
        ticker: str,
        *,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        as_of: date,
    ) -> HistoryResponse | None:
        stock = await self._repository.get_stock(ticker)
        if not stock:
            return None
        bars = await self._repository.get_history(
            ticker, date_from=date_from, date_to=date_to, limit=limit
        )
        latest = bars[-1].trade_date if bars else None
        expected = expected_latest_trade_date(as_of)
        return HistoryResponse(
            ticker=stock.ticker,
            company_name=stock.company_name,
            date_from=bars[0].trade_date if bars else date_from,
            date_to=bars[-1].trade_date if bars else date_to,
            latest_trade_date=latest,
            is_stale=latest is None or latest < expected,
            is_mock=self._is_mock,
            source=self._provider,
            bars=[
                HistoryBarResponse(
                    date=bar.trade_date,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    previous=bar.previous,
                    volume_shares=bar.volume_shares,
                    volume_lots=Decimal(bar.volume_shares) / Decimal(100),
                    value_idr=bar.value_idr,
                    frequency=bar.frequency,
                    frequency_analyzer_raw_shares=frequency_analyzer_raw(
                        bar.volume_shares, bar.frequency, unit="shares"
                    ),
                    frequency_analyzer_raw_lots=frequency_analyzer_raw(
                        bar.volume_shares, bar.frequency, unit="lots"
                    ),
                )
                for bar in bars
            ],
        )

    async def get_status(self, *, as_of: date) -> DataStatusResponse:
        latest = await self._repository.latest_trade_date()
        ingestion = await self._repository.latest_ingestion()
        expected = expected_latest_trade_date(as_of)
        return DataStatusResponse(
            latest_trade_date=latest,
            expected_trade_date=expected,
            is_stale=latest is None or latest < expected,
            is_mock=self._is_mock,
            provider=self._provider,
            repository=self._repository.kind,
            ingestion=IngestionStatusResponse(
                provider=ingestion.provider,
                status=ingestion.status,
                finished_at=ingestion.finished_at,
                rows_received=ingestion.rows_received,
            )
            if ingestion
            else None,
        )
