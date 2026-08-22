from datetime import UTC, date, datetime

from app.repositories.base import IngestionStatus, StockSnapshot
from app.schemas.domain import MarketBar, StockIdentity


class MemoryMarketRepository:
    kind = "memory"

    def __init__(self) -> None:
        self._stocks: dict[str, StockIdentity] = {}
        self._bars: dict[str, dict[date, MarketBar]] = {}
        self._runs: dict[int, IngestionStatus] = {}
        self._next_run_id = 1

    async def list_stocks(self) -> list[StockSnapshot]:
        snapshots: list[StockSnapshot] = []
        for ticker in sorted(self._stocks):
            bars = sorted(self._bars.get(ticker, {}).values(), key=lambda bar: bar.trade_date)
            latest = bars[-1] if bars else None
            snapshots.append(
                StockSnapshot(
                    stock=self._stocks[ticker],
                    latest_close=latest.close if latest else None,
                    previous=latest.previous if latest else None,
                    latest_trade_date=latest.trade_date if latest else None,
                    sparkline=[bar.close for bar in bars[-30:]],
                )
            )
        return snapshots

    async def get_stock(self, ticker: str) -> StockIdentity | None:
        return self._stocks.get(ticker.upper())

    async def get_history(
        self, ticker: str, *, date_from: date | None, date_to: date | None, limit: int
    ) -> list[MarketBar]:
        bars = sorted(self._bars.get(ticker.upper(), {}).values(), key=lambda bar: bar.trade_date)
        if date_from:
            bars = [bar for bar in bars if bar.trade_date >= date_from]
        if date_to:
            bars = [bar for bar in bars if bar.trade_date <= date_to]
        return bars[-limit:]

    async def upsert_history(self, stock: StockIdentity, bars: list[MarketBar]) -> tuple[int, int]:
        self._stocks[stock.ticker] = stock
        ticker_bars = self._bars.setdefault(stock.ticker, {})
        inserted = sum(1 for bar in bars if bar.trade_date not in ticker_bars)
        updated = len(bars) - inserted
        ticker_bars.update({bar.trade_date: bar for bar in bars})
        return inserted, updated

    async def latest_trade_date(self) -> date | None:
        dates = [trade_date for bars in self._bars.values() for trade_date in bars]
        return max(dates) if dates else None

    async def start_ingestion(self, provider: str, requested_date: date | None) -> int:
        run_id = self._next_run_id
        self._next_run_id += 1
        self._runs[run_id] = IngestionStatus(provider, "running", None, 0)
        return run_id

    async def finish_ingestion(
        self,
        run_id: int,
        *,
        status: str,
        rows_received: int,
        rows_inserted: int,
        rows_updated: int,
        error_message: str | None = None,
    ) -> None:
        del rows_inserted, rows_updated, error_message
        current = self._runs[run_id]
        self._runs[run_id] = IngestionStatus(
            current.provider, status, datetime.now(UTC), rows_received
        )

    async def latest_ingestion(self) -> IngestionStatus | None:
        return self._runs[max(self._runs)] if self._runs else None
