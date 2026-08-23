from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.schemas.domain import MarketBar, StockIdentity


@dataclass(frozen=True)
class StockSnapshot:
    stock: StockIdentity
    latest_close: Decimal | None
    previous: Decimal | None
    latest_trade_date: date | None
    sparkline: list[Decimal]


@dataclass(frozen=True)
class IngestionStatus:
    provider: str
    status: str
    finished_at: datetime | None
    rows_received: int


@dataclass(frozen=True)
class HistoryState:
    row_count: int
    latest_trade_date: date | None


class MarketRepository(Protocol):
    kind: str

    async def list_stocks(self, query: str | None = None) -> list[StockSnapshot]: ...

    async def sync_stock_universe(
        self, stocks: list[StockIdentity], *, deactivate_missing: bool
    ) -> tuple[int, int, int]: ...

    async def get_stock(self, ticker: str) -> StockIdentity | None: ...

    async def get_history(
        self, ticker: str, *, date_from: date | None, date_to: date | None, limit: int | None
    ) -> list[MarketBar]: ...

    async def upsert_history(
        self, stock: StockIdentity, bars: list[MarketBar]
    ) -> tuple[int, int]: ...

    async def latest_trade_date(self, ticker: str | None = None) -> date | None: ...

    async def history_state(self, ticker: str) -> HistoryState: ...

    async def update_checkpoint(
        self,
        ticker: str,
        *,
        provider: str,
        dataset: str,
        status: str,
        last_successful_trade_date: date | None = None,
        error_message: str | None = None,
    ) -> None: ...

    async def checkpoint_tickers(
        self, *, provider: str, dataset: str, status: str
    ) -> list[str]: ...

    async def resumable_tickers(
        self, *, provider: str, dataset: str, include_terminal: bool = False
    ) -> list[str]: ...

    async def start_ingestion(self, provider: str, requested_date: date | None) -> int: ...

    async def finish_ingestion(
        self,
        run_id: int,
        *,
        status: str,
        rows_received: int,
        rows_inserted: int,
        rows_updated: int,
        error_message: str | None = None,
    ) -> None: ...

    async def latest_ingestion(
        self, *, successful_only: bool = False
    ) -> IngestionStatus | None: ...
