from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import Database
from app.models.market import DailyMarketData, IngestionRun, Stock
from app.repositories.base import IngestionStatus, StockSnapshot
from app.schemas.domain import MarketBar, StockIdentity


class PostgresMarketRepository:
    kind = "supabase-postgres"

    def __init__(self, database: Database):
        self._database = database

    async def list_stocks(self) -> list[StockSnapshot]:
        async with self._database.session() as session:
            stocks = list((await session.scalars(select(Stock).where(Stock.is_active))).all())
            if not stocks:
                return []
            ranked = (
                select(
                    DailyMarketData,
                    func.row_number()
                    .over(
                        partition_by=DailyMarketData.stock_id,
                        order_by=DailyMarketData.trade_date.desc(),
                    )
                    .label("rank"),
                )
                .where(DailyMarketData.stock_id.in_([stock.id for stock in stocks]))
                .subquery()
            )
            rows = (
                await session.execute(
                    select(ranked).where(ranked.c.rank <= 30).order_by(ranked.c.trade_date)
                )
            ).mappings()
            grouped: dict[int, list[dict[str, object]]] = {}
            for row in rows:
                grouped.setdefault(int(row["stock_id"]), []).append(dict(row))

        output: list[StockSnapshot] = []
        for stock in sorted(stocks, key=lambda item: item.ticker):
            stock_rows = grouped.get(stock.id, [])
            latest = stock_rows[-1] if stock_rows else None
            output.append(
                StockSnapshot(
                    stock=_stock_identity(stock),
                    latest_close=latest["close"] if latest else None,  # type: ignore[arg-type]
                    previous=latest["previous"] if latest else None,  # type: ignore[arg-type]
                    latest_trade_date=latest["trade_date"] if latest else None,  # type: ignore[arg-type]
                    sparkline=[row["close"] for row in stock_rows],  # type: ignore[misc]
                )
            )
        return output

    async def get_stock(self, ticker: str) -> StockIdentity | None:
        async with self._database.session() as session:
            stock = await session.scalar(select(Stock).where(Stock.ticker == ticker.upper()))
            return _stock_identity(stock) if stock else None

    async def get_history(
        self, ticker: str, *, date_from: date | None, date_to: date | None, limit: int
    ) -> list[MarketBar]:
        async with self._database.session() as session:
            statement = (
                select(DailyMarketData)
                .join(Stock, Stock.id == DailyMarketData.stock_id)
                .where(Stock.ticker == ticker.upper())
            )
            if date_from:
                statement = statement.where(DailyMarketData.trade_date >= date_from)
            if date_to:
                statement = statement.where(DailyMarketData.trade_date <= date_to)
            statement = statement.order_by(DailyMarketData.trade_date.desc()).limit(limit)
            rows = list((await session.scalars(statement)).all())
            rows.reverse()
            return [_market_bar(row) for row in rows]

    async def upsert_history(self, stock: StockIdentity, bars: list[MarketBar]) -> tuple[int, int]:
        if not bars:
            return 0, 0
        async with self._database.session() as session, session.begin():
            stock_statement = (
                pg_insert(Stock)
                .values(
                    ticker=stock.ticker,
                    company_name=stock.company_name,
                    sector=stock.sector,
                    subsector=stock.subsector,
                    is_active=True,
                )
                .on_conflict_do_update(
                    index_elements=[Stock.ticker],
                    set_={
                        "company_name": stock.company_name,
                        "sector": stock.sector,
                        "subsector": stock.subsector,
                        "is_active": True,
                        "updated_at": func.now(),
                    },
                )
                .returning(Stock.id)
            )
            stock_id = int((await session.execute(stock_statement)).scalar_one())
            dates = [bar.trade_date for bar in bars]
            existing_dates = set(
                (
                    await session.scalars(
                        select(DailyMarketData.trade_date).where(
                            DailyMarketData.stock_id == stock_id,
                            DailyMarketData.trade_date.in_(dates),
                        )
                    )
                ).all()
            )
            values = [
                {"stock_id": stock_id, **bar.model_dump(exclude={"ingested_at"})} for bar in bars
            ]
            insert_statement = pg_insert(DailyMarketData).values(values)
            update_columns = {
                column: getattr(insert_statement.excluded, column)
                for column in values[0]
                if column not in {"stock_id", "trade_date"}
            }
            update_columns["updated_at"] = func.now()
            await session.execute(
                insert_statement.on_conflict_do_update(
                    index_elements=[DailyMarketData.stock_id, DailyMarketData.trade_date],
                    set_=update_columns,
                )
            )
        inserted = len(set(dates) - existing_dates)
        return inserted, len(bars) - inserted

    async def latest_trade_date(self) -> date | None:
        async with self._database.session() as session:
            return await session.scalar(select(func.max(DailyMarketData.trade_date)))

    async def start_ingestion(self, provider: str, requested_date: date | None) -> int:
        async with self._database.session() as session, session.begin():
            run = IngestionRun(provider=provider, status="running", requested_date=requested_date)
            session.add(run)
            await session.flush()
            return run.id

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
        async with self._database.session() as session, session.begin():
            run = await session.get(IngestionRun, run_id)
            if run is None:
                raise LookupError(f"ingestion run {run_id} not found")
            run.status = status
            run.finished_at = datetime.now(UTC)
            run.rows_received = rows_received
            run.rows_inserted = rows_inserted
            run.rows_updated = rows_updated
            run.error_message = error_message[:1000] if error_message else None

    async def latest_ingestion(self) -> IngestionStatus | None:
        async with self._database.session() as session:
            run = await session.scalar(
                select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
            )
            if not run:
                return None
            return IngestionStatus(run.provider, run.status, run.finished_at, run.rows_received)


def _stock_identity(stock: Stock) -> StockIdentity:
    return StockIdentity(
        ticker=stock.ticker,
        company_name=stock.company_name,
        sector=stock.sector,
        subsector=stock.subsector,
    )


def _market_bar(row: DailyMarketData) -> MarketBar:
    return MarketBar(
        trade_date=row.trade_date,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        previous=row.previous,
        volume_shares=row.volume_shares,
        value_idr=row.value_idr,
        frequency=row.frequency,
        foreign_buy_shares=row.foreign_buy_shares,
        foreign_sell_shares=row.foreign_sell_shares,
        non_regular_volume_shares=row.non_regular_volume_shares,
        non_regular_value_idr=row.non_regular_value_idr,
        non_regular_frequency=row.non_regular_frequency,
        source=row.source,
        ingested_at=row.ingested_at,
    )
