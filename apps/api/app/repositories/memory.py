from datetime import UTC, date, datetime

from app.repositories.base import HistoryState, IngestionStatus, StockSnapshot
from app.schemas.domain import MarketBar, StockIdentity


class MemoryMarketRepository:
    kind = "memory"

    def __init__(self) -> None:
        self._stocks: dict[str, StockIdentity] = {}
        self._active: set[str] = set()
        self._bars: dict[str, dict[date, MarketBar]] = {}
        self._runs: dict[int, IngestionStatus] = {}
        self._checkpoints: dict[tuple[str, str, str], tuple[str, date | None]] = {}
        self._next_run_id = 1

    async def list_stocks(self, query: str | None = None) -> list[StockSnapshot]:
        snapshots: list[StockSnapshot] = []
        normalized_query = query.strip().lower() if query else None
        for ticker in sorted(self._active):
            stock = self._stocks[ticker]
            if (
                normalized_query
                and normalized_query not in ticker.lower()
                and normalized_query not in stock.company_name.lower()
            ):
                continue
            bars = sorted(self._bars.get(ticker, {}).values(), key=lambda bar: bar.trade_date)
            latest = bars[-1] if bars else None
            snapshots.append(
                StockSnapshot(
                    stock=stock,
                    latest_close=latest.close if latest else None,
                    previous=latest.previous if latest else None,
                    latest_trade_date=latest.trade_date if latest else None,
                    sparkline=[bar.close for bar in bars[-30:]],
                )
            )
        return snapshots

    async def sync_stock_universe(
        self, stocks: list[StockIdentity], *, deactivate_missing: bool
    ) -> tuple[int, int, int]:
        incoming = {stock.ticker: stock for stock in stocks}
        inserted = len(set(incoming) - set(self._stocks))
        updated = len(incoming) - inserted
        previous_active = set(self._active)
        self._stocks.update(incoming)
        self._active.update(incoming)
        deactivated = 0
        if deactivate_missing:
            missing = previous_active - set(incoming)
            self._active.difference_update(missing)
            deactivated = len(missing)
        return inserted, updated, deactivated

    async def get_stock(self, ticker: str) -> StockIdentity | None:
        return self._stocks.get(ticker.upper())

    async def get_history(
        self, ticker: str, *, date_from: date | None, date_to: date | None, limit: int | None
    ) -> list[MarketBar]:
        bars = sorted(self._bars.get(ticker.upper(), {}).values(), key=lambda bar: bar.trade_date)
        if date_from:
            bars = [bar for bar in bars if bar.trade_date >= date_from]
        if date_to:
            bars = [bar for bar in bars if bar.trade_date <= date_to]
        return bars[-limit:] if limit is not None else bars

    async def upsert_history(self, stock: StockIdentity, bars: list[MarketBar]) -> tuple[int, int]:
        self._stocks[stock.ticker] = stock
        self._active.add(stock.ticker)
        ticker_bars = self._bars.setdefault(stock.ticker, {})
        inserted = sum(1 for bar in bars if bar.trade_date not in ticker_bars)
        updated = len(bars) - inserted
        ticker_bars.update({bar.trade_date: bar for bar in bars})
        return inserted, updated

    async def latest_trade_date(self, ticker: str | None = None) -> date | None:
        ticker_bars = [self._bars.get(ticker.upper(), {})] if ticker else self._bars.values()
        dates = [trade_date for bars in ticker_bars for trade_date in bars]
        return max(dates) if dates else None

    async def history_state(self, ticker: str) -> HistoryState:
        bars = self._bars.get(ticker.upper(), {})
        return HistoryState(len(bars), max(bars) if bars else None)

    async def update_checkpoint(
        self,
        ticker: str,
        *,
        provider: str,
        dataset: str,
        status: str,
        last_successful_trade_date: date | None = None,
        error_message: str | None = None,
    ) -> None:
        del error_message
        key = (provider, dataset, ticker.upper())
        previous = self._checkpoints.get(key)
        successful_date = (
            last_successful_trade_date
            if status == "succeeded"
            else (previous[1] if previous else None)
        )
        self._checkpoints[key] = (status, successful_date)

    async def checkpoint_tickers(self, *, provider: str, dataset: str, status: str) -> list[str]:
        return sorted(
            ticker
            for (item_provider, item_dataset, ticker), value in self._checkpoints.items()
            if item_provider == provider and item_dataset == dataset and value[0] == status
        )

    async def resumable_tickers(self, *, provider: str, dataset: str) -> list[str]:
        output: list[str] = []
        for ticker in self._active:
            checkpoint = self._checkpoints.get((provider, dataset, ticker))
            if checkpoint is None or checkpoint[0] in {"failed", "running"}:
                output.append(ticker)
        return sorted(output)

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

    async def latest_ingestion(self, *, successful_only: bool = False) -> IngestionStatus | None:
        runs = [
            (run_id, run)
            for run_id, run in self._runs.items()
            if not successful_only or run.status == "succeeded"
        ]
        return max(runs, default=(0, None), key=lambda item: item[0])[1]
