from datetime import date
from typing import Protocol

from app.schemas.domain import ProviderHistory


class MarketDataProvider(Protocol):
    name: str

    async def get_stock_history(
        self,
        ticker: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 260,
    ) -> ProviderHistory: ...

    async def get_daily_market_summary(
        self, *, trade_date: date | None = None
    ) -> list[ProviderHistory]: ...
