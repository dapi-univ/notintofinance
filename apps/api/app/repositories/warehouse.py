import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Database, UnsafeDatabaseTarget
from app.models.market import DailyMarketData, Stock
from app.models.warehouse import (
    BrokerFlowDaily,
    DataQualityEvent,
    IngestionCursor,
    InstrumentProviderMapping,
    OrderbookLevel,
    OrderbookSnapshot,
    ProviderRequestLedger,
    RawProviderPayload,
    TradebookAggregate,
    TradePrint,
)
from app.providers.transport import ProviderRequestEvent
from app.schemas.warehouse import (
    BrokerFlowRecord,
    IngestionCursorState,
    InstrumentMappingRecord,
    MarketPriorityCandidate,
    OrderbookSnapshotRecord,
    RawPayloadRecord,
    TradebookAggregateRecord,
    TradePrintRecord,
)

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "subscription",
    "token",
}


class PostgresWarehouseRepository:
    def __init__(self, database: Database, *, raw_retention_days: int = 7) -> None:
        self._database = database
        self._raw_retention_days = raw_retention_days

    async def record_request(self, event: ProviderRequestEvent) -> None:
        async with self._database.session() as session, session.begin():
            session.add(ProviderRequestLedger(**event.__dict__))

    async def requests_today(self, provider: str) -> int:
        today = datetime.now(UTC).date()
        async with self._database.session() as session:
            count = await session.scalar(
                select(func.count(ProviderRequestLedger.id)).where(
                    ProviderRequestLedger.provider == provider,
                    func.date(ProviderRequestLedger.requested_at) == today,
                )
            )
            return int(count or 0)

    async def latest_quota(self, provider: str) -> dict[str, object] | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(ProviderRequestLedger)
                .where(ProviderRequestLedger.provider == provider)
                .order_by(ProviderRequestLedger.requested_at.desc())
                .limit(1)
            )
            if not row:
                return None
            return {
                "provider": row.provider,
                "observed_at": row.completed_at,
                "limit": row.quota_limit,
                "remaining_minute": row.quota_remaining_minute,
                "remaining_month": row.quota_remaining_month,
                "plan_expired": row.plan_expired,
                "warning": row.warning,
            }

    async def upsert_mapping(self, mapping: InstrumentMappingRecord) -> None:
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, mapping.ticker)
            statement = pg_insert(InstrumentProviderMapping).values(
                stock_id=stock_id,
                provider=mapping.provider,
                provider_instrument_id=mapping.provider_instrument_id,
                provider_ticker=mapping.provider_ticker,
                exchange=mapping.exchange,
                mapping_status=mapping.mapping_status,
                source=mapping.source,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="instrument_provider_mappings_stock_provider_key",
                    set_={
                        "provider_instrument_id": statement.excluded.provider_instrument_id,
                        "provider_ticker": statement.excluded.provider_ticker,
                        "exchange": statement.excluded.exchange,
                        "mapping_status": statement.excluded.mapping_status,
                        "last_observed_at": func.now(),
                        "source": statement.excluded.source,
                    },
                )
            )

    async def mapping(
        self, ticker: str, provider: str = "pluang"
    ) -> InstrumentMappingRecord | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(InstrumentProviderMapping)
                .join(Stock, Stock.id == InstrumentProviderMapping.stock_id)
                .where(
                    Stock.ticker == ticker.upper(), InstrumentProviderMapping.provider == provider
                )
            )
            if not row:
                return None
            return InstrumentMappingRecord(
                ticker=ticker.upper(),
                provider=row.provider,
                provider_instrument_id=row.provider_instrument_id,
                provider_ticker=row.provider_ticker,
                exchange=row.exchange,
                mapping_status=row.mapping_status,
                source=row.source,
            )

    async def mapping_candidates(self, *, include_terminal: bool = False) -> list[str]:
        async with self._database.session() as session:
            join_condition = and_(
                InstrumentProviderMapping.stock_id == Stock.id,
                InstrumentProviderMapping.provider == "pluang",
            )
            statement = (
                select(Stock.ticker)
                .outerjoin(InstrumentProviderMapping, join_condition)
                .where(Stock.is_active)
            )
            if not include_terminal:
                statement = statement.where(
                    (InstrumentProviderMapping.id.is_(None))
                    | (InstrumentProviderMapping.mapping_status == "transient_failure")
                )
            return list((await session.scalars(statement.order_by(Stock.ticker))).all())

    async def stage_raw_payload(self, record: RawPayloadRecord) -> None:
        sanitized = _sanitize(record.payload)
        material = json.dumps(sanitized, sort_keys=True, separators=(",", ":"), default=str)
        response_hash = hashlib.sha256(material.encode()).hexdigest()
        fetched_at = datetime.now(UTC)
        async with self._database.session() as session, session.begin():
            statement = pg_insert(RawProviderPayload).values(
                provider=record.provider,
                gateway=record.gateway,
                source_provider=record.source_provider,
                dataset=record.dataset,
                instrument_key=record.instrument_key,
                date_from=record.date_from,
                date_to=record.date_to,
                cursor_value=record.cursor_value,
                response_hash=response_hash,
                payload=sanitized,
                fetched_at=fetched_at,
                expires_at=fetched_at + timedelta(days=self._raw_retention_days),
                normalization_status=record.normalization_status,
                normalization_error=(record.normalization_error or "")[:1000] or None,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="raw_provider_payloads_provider_hash_key",
                    set_={
                        "fetched_at": statement.excluded.fetched_at,
                        "expires_at": statement.excluded.expires_at,
                        "normalization_status": statement.excluded.normalization_status,
                        "normalization_error": statement.excluded.normalization_error,
                    },
                )
            )

    async def purge_expired_raw_payloads(self) -> int:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(RawProviderPayload).where(
                    RawProviderPayload.expires_at <= datetime.now(UTC)
                )
            )
            return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def upsert_broker_flow(self, records: list[BrokerFlowRecord]) -> tuple[int, int]:
        if not records:
            return 0, 0
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, records[0].ticker)
            identities = [
                (record.trade_date_from, record.trade_date_to, record.side, record.broker_code)
                for record in records
            ]
            existing = set(
                (
                    await session.execute(
                        select(
                            BrokerFlowDaily.trade_date_from,
                            BrokerFlowDaily.trade_date_to,
                            BrokerFlowDaily.side,
                            BrokerFlowDaily.broker_code,
                        ).where(
                            BrokerFlowDaily.stock_id == stock_id,
                            BrokerFlowDaily.provider == records[0].provider,
                            tuple_(
                                BrokerFlowDaily.trade_date_from,
                                BrokerFlowDaily.trade_date_to,
                                BrokerFlowDaily.side,
                                BrokerFlowDaily.broker_code,
                            ).in_(identities),
                        )
                    )
                ).all()
            )
            values = [
                {"stock_id": stock_id, **record.model_dump(exclude={"ticker"})}
                for record in records
            ]
            statement = pg_insert(BrokerFlowDaily).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="broker_flow_daily_identity_key",
                    set_={
                        "broker_name": statement.excluded.broker_name,
                        "rank": statement.excluded.rank,
                        "lots": statement.excluded.lots,
                        "shares": statement.excluded.shares,
                        "value_idr": statement.excluded.value_idr,
                        "average_price": statement.excluded.average_price,
                        "source_scope": statement.excluded.source_scope,
                        "source_top_n": statement.excluded.source_top_n,
                        "ingested_at": func.now(),
                    },
                )
            )
        inserted = len(set(identities) - existing)
        return inserted, len(records) - inserted

    async def upsert_tradebook(
        self, records: list[TradebookAggregateRecord]
    ) -> tuple[int, int]:
        if not records:
            return 0, 0
        first = records[0]
        if any(
            (row.ticker, row.provider, row.trade_date)
            != (first.ticker, first.provider, first.trade_date)
            for row in records
        ):
            raise ValueError("tradebook upsert requires one ticker/provider/session")
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, first.ticker)
            identities = [(row.view_type, row.bucket_key) for row in records]
            existing = set(
                (
                    await session.execute(
                        select(
                            TradebookAggregate.view_type,
                            TradebookAggregate.bucket_key,
                        ).where(
                            TradebookAggregate.stock_id == stock_id,
                            TradebookAggregate.provider == first.provider,
                            TradebookAggregate.trade_date == first.trade_date,
                            tuple_(
                                TradebookAggregate.view_type,
                                TradebookAggregate.bucket_key,
                            ).in_(identities),
                        )
                    )
                ).all()
            )
            values = [
                {"stock_id": stock_id, **row.model_dump(exclude={"ticker"})}
                for row in records
            ]
            statement = pg_insert(TradebookAggregate).values(values)
            excluded = statement.excluded
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="tradebook_aggregates_identity_key",
                    set_={
                        "price": excluded.price,
                        "time_bucket": excluded.time_bucket,
                        "buy_frequency": excluded.buy_frequency,
                        "buy_lots": excluded.buy_lots,
                        "sell_frequency": excluded.sell_frequency,
                        "sell_lots": excluded.sell_lots,
                        "pre_frequency": excluded.pre_frequency,
                        "pre_lots": excluded.pre_lots,
                        "post_frequency": excluded.post_frequency,
                        "post_lots": excluded.post_lots,
                        "total_frequency": excluded.total_frequency,
                        "total_lots": excluded.total_lots,
                        "source_scope": excluded.source_scope,
                        "ingested_at": func.now(),
                    },
                )
            )
        inserted = len(set(identities) - existing)
        return inserted, len(records) - inserted

    async def upsert_trade_prints(self, records: list[TradePrintRecord]) -> tuple[int, int]:
        if not records:
            return 0, 0
        if self._database.is_managed_supabase and any(
            _is_synthetic_identity(record.provider_sequence) for record in records
        ):
            raise UnsafeDatabaseTarget("synthetic trade identities cannot be written to Supabase")
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, records[0].ticker)
            identities = [(record.trade_date, record.provider_sequence) for record in records]
            existing = set(
                (
                    await session.execute(
                        select(TradePrint.trade_date, TradePrint.provider_sequence).where(
                            TradePrint.stock_id == stock_id,
                            TradePrint.provider == records[0].provider,
                            tuple_(TradePrint.trade_date, TradePrint.provider_sequence).in_(
                                identities
                            ),
                        )
                    )
                ).all()
            )
            values = [
                {"stock_id": stock_id, **record.model_dump(exclude={"ticker"})}
                for record in records
            ]
            statement = pg_insert(TradePrint).values(values)
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="trade_prints_identity_key",
                    set_={
                        "executed_at": statement.excluded.executed_at,
                        "price": statement.excluded.price,
                        "lots": statement.excluded.lots,
                        "shares": statement.excluded.shares,
                        "aggressor_action": statement.excluded.aggressor_action,
                        "fetched_at": func.now(),
                    },
                )
            )
        inserted = len(set(identities) - existing)
        return inserted, len(records) - inserted

    async def insert_orderbook_snapshot(self, record: OrderbookSnapshotRecord) -> int:
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, record.ticker)
            statement = (
                pg_insert(OrderbookSnapshot)
                .values(
                    stock_id=stock_id,
                    provider=record.provider,
                    observed_at=record.observed_at,
                    best_bid=record.best_bid,
                    best_ask=record.best_ask,
                    spread=record.spread,
                )
                .on_conflict_do_update(
                    constraint="orderbook_snapshots_identity_key",
                    set_={
                        "best_bid": record.best_bid,
                        "best_ask": record.best_ask,
                        "spread": record.spread,
                        "fetched_at": func.now(),
                    },
                )
                .returning(OrderbookSnapshot.id)
            )
            snapshot_id = int((await session.execute(statement)).scalar_one())
            await session.execute(
                delete(OrderbookLevel).where(OrderbookLevel.snapshot_id == snapshot_id)
            )
            if record.levels:
                await session.execute(
                    pg_insert(OrderbookLevel).values(
                        [
                            {"snapshot_id": snapshot_id, **level.model_dump()}
                            for level in record.levels
                        ]
                    )
                )
            return snapshot_id

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
    ) -> None:
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, ticker)
            statement = pg_insert(IngestionCursor).values(
                provider=provider,
                dataset=dataset,
                stock_id=stock_id,
                instrument_key=instrument_key,
                session_date=session_date,
                cursor_value=cursor_value,
                high_water_mark=high_water_mark,
                status=status,
                error_message=(error_message or "")[:1000] or None,
                collection_filter=_sanitize(collection_filter or {}),
                collection_floor_idr=collection_floor_idr,
                rows_fetched=rows_fetched,
                rows_retained=rows_retained,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    constraint="ingestion_cursors_identity_key",
                    set_={
                        "stock_id": statement.excluded.stock_id,
                        "session_date": statement.excluded.session_date,
                        "cursor_value": statement.excluded.cursor_value,
                        "high_water_mark": statement.excluded.high_water_mark,
                        "status": statement.excluded.status,
                        "attempt_count": IngestionCursor.attempt_count + 1,
                        "error_message": statement.excluded.error_message,
                        "collection_filter": statement.excluded.collection_filter,
                        "collection_floor_idr": statement.excluded.collection_floor_idr,
                        "rows_fetched": statement.excluded.rows_fetched,
                        "rows_retained": statement.excluded.rows_retained,
                        "updated_at": func.now(),
                    },
                )
            )

    async def ingestion_cursor(
        self,
        *,
        ticker: str,
        provider: str,
        dataset: str,
        session_date: date,
    ) -> IngestionCursorState | None:
        async with self._database.session() as session:
            row = await session.scalar(
                select(IngestionCursor)
                .join(Stock, Stock.id == IngestionCursor.stock_id)
                .where(
                    Stock.ticker == ticker.upper(),
                    IngestionCursor.provider == provider,
                    IngestionCursor.dataset == dataset,
                    IngestionCursor.session_date == session_date,
                )
            )
            if not row:
                return None
            return IngestionCursorState(
                instrument_key=row.instrument_key,
                session_date=row.session_date,
                cursor_value=row.cursor_value,
                high_water_mark=row.high_water_mark,
                status=row.status,
                collection_filter=row.collection_filter,
                collection_floor_idr=row.collection_floor_idr,
                rows_fetched=row.rows_fetched,
                rows_retained=row.rows_retained,
            )

    async def collection_candidates(
        self, *, mapped_only: bool = True
    ) -> list[MarketPriorityCandidate]:
        latest_dates = (
            select(
                DailyMarketData.stock_id.label("stock_id"),
                func.max(DailyMarketData.trade_date).label("trade_date"),
            )
            .group_by(DailyMarketData.stock_id)
            .subquery()
        )
        async with self._database.session() as session:
            statement = (
                select(
                    Stock.ticker,
                    DailyMarketData.close,
                    DailyMarketData.listed_shares,
                    DailyMarketData.value_idr,
                    DailyMarketData.frequency,
                )
                .outerjoin(latest_dates, latest_dates.c.stock_id == Stock.id)
                .outerjoin(
                    DailyMarketData,
                    and_(
                        DailyMarketData.stock_id == Stock.id,
                        DailyMarketData.trade_date == latest_dates.c.trade_date,
                    ),
                )
                .where(Stock.is_active)
            )
            if mapped_only:
                statement = statement.join(
                    InstrumentProviderMapping,
                    and_(
                        InstrumentProviderMapping.stock_id == Stock.id,
                        InstrumentProviderMapping.provider == "pluang",
                        InstrumentProviderMapping.mapping_status == "mapped",
                    ),
                )
            rows = (await session.execute(statement.order_by(Stock.ticker))).all()
            return [
                MarketPriorityCandidate(
                    ticker=row.ticker,
                    latest_close=row.close,
                    listed_shares=row.listed_shares,
                    value_idr=row.value_idr,
                    frequency=row.frequency,
                )
                for row in rows
            ]

    async def record_quality_event(
        self,
        *,
        provider: str,
        dataset: str,
        reason_code: str,
        retryable: bool,
        terminal: bool,
        ticker: str | None = None,
        severity: str = "error",
        context: dict[str, object] | None = None,
    ) -> None:
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, ticker) if ticker else None
            session.add(
                DataQualityEvent(
                    provider=provider,
                    dataset=dataset,
                    stock_id=stock_id,
                    severity=severity,
                    reason_code=reason_code,
                    context=_sanitize(context or {}),
                    retryable=retryable,
                    is_terminal=terminal,
                    attempt_count=1,
                )
            )

    async def has_terminal_quality_block(
        self, *, ticker: str, provider: str, dataset: str
    ) -> bool:
        async with self._database.session() as session:
            return bool(
                await session.scalar(
                    select(DataQualityEvent.id)
                    .join(Stock, Stock.id == DataQualityEvent.stock_id)
                    .where(
                        Stock.ticker == ticker.upper(),
                        DataQualityEvent.provider == provider,
                        DataQualityEvent.dataset == dataset,
                        DataQualityEvent.is_terminal,
                        DataQualityEvent.resolved_at.is_(None),
                    )
                    .limit(1)
                )
            )

    async def resolve_quality_event(
        self,
        *,
        ticker: str,
        provider: str,
        dataset: str,
        reason_code: str,
    ) -> int:
        async with self._database.session() as session, session.begin():
            stock_id = await self._stock_id(session, ticker)
            result = await session.scalars(
                update(DataQualityEvent)
                .where(
                    DataQualityEvent.stock_id == stock_id,
                    DataQualityEvent.provider == provider,
                    DataQualityEvent.dataset == dataset,
                    DataQualityEvent.reason_code == reason_code,
                    DataQualityEvent.is_terminal,
                    DataQualityEvent.resolved_at.is_(None),
                )
                .values(resolved_at=func.now())
                .returning(DataQualityEvent.id)
            )
            return len(result.all())

    @asynccontextmanager
    async def advisory_lock(self, lock_name: str) -> AsyncIterator[None]:
        async with self._database.session() as session:
            acquired = bool(
                await session.scalar(select(func.pg_try_advisory_lock(func.hashtext(lock_name))))
            )
            if not acquired:
                raise RuntimeError(f"ingestion lock already held: {lock_name}")
            try:
                yield
            finally:
                await session.scalar(select(func.pg_advisory_unlock(func.hashtext(lock_name))))

    async def broker_flow(
        self, ticker: str, date_from: date, date_to: date
    ) -> list[BrokerFlowDaily]:
        async with self._database.session() as session:
            return list(
                (
                    await session.scalars(
                        select(BrokerFlowDaily)
                        .join(Stock, Stock.id == BrokerFlowDaily.stock_id)
                        .where(
                            Stock.ticker == ticker.upper(),
                            BrokerFlowDaily.trade_date_to >= date_from,
                            BrokerFlowDaily.trade_date_from <= date_to,
                        )
                        .order_by(
                            BrokerFlowDaily.trade_date_to,
                            BrokerFlowDaily.side,
                            BrokerFlowDaily.rank,
                        )
                    )
                ).all()
            )

    async def trades(
        self,
        ticker: str,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        cursor: tuple[datetime, int] | None,
    ) -> list[TradePrint]:
        async with self._database.session() as session:
            statement = (
                select(TradePrint)
                .join(Stock, Stock.id == TradePrint.stock_id)
                .where(
                    Stock.ticker == ticker.upper(),
                    TradePrint.trade_date.between(date_from, date_to),
                )
                .order_by(TradePrint.executed_at.desc(), TradePrint.id.desc())
                .limit(limit)
            )
            if cursor is not None:
                statement = statement.where(
                    tuple_(TradePrint.executed_at, TradePrint.id) < cursor
                )
            return list((await session.scalars(statement)).all())

    async def trades_by_sequences(
        self, ticker: str, trade_date: date, sequences: list[str]
    ) -> list[TradePrint]:
        if not sequences:
            return []
        async with self._database.session() as session:
            return list(
                (
                    await session.scalars(
                        select(TradePrint)
                        .join(Stock, Stock.id == TradePrint.stock_id)
                        .where(
                            Stock.ticker == ticker.upper(),
                            TradePrint.provider == "pluang",
                            TradePrint.trade_date == trade_date,
                            TradePrint.provider_sequence.in_(sequences),
                        )
                    )
                ).all()
            )

    async def latest_orderbook(
        self, ticker: str
    ) -> tuple[OrderbookSnapshot, list[OrderbookLevel]] | None:
        async with self._database.session() as session:
            snapshot = await session.scalar(
                select(OrderbookSnapshot)
                .join(Stock, Stock.id == OrderbookSnapshot.stock_id)
                .where(Stock.ticker == ticker.upper())
                .order_by(OrderbookSnapshot.observed_at.desc())
                .limit(1)
            )
            if not snapshot:
                return None
            levels = list(
                (
                    await session.scalars(
                        select(OrderbookLevel)
                        .where(OrderbookLevel.snapshot_id == snapshot.id)
                        .order_by(OrderbookLevel.side, OrderbookLevel.level_rank)
                    )
                ).all()
            )
            return snapshot, levels

    async def coverage(self) -> dict[str, object]:
        async with self._database.session() as session:
            stock_count = int(
                await session.scalar(select(func.count(Stock.id)).where(Stock.is_active)) or 0
            )
            history_count = int(
                await session.scalar(select(func.count(func.distinct(DailyMarketData.stock_id))))
                or 0
            )
            mapping_count = int(
                await session.scalar(
                    select(func.count(InstrumentProviderMapping.id)).where(
                        InstrumentProviderMapping.provider == "pluang",
                        InstrumentProviderMapping.mapping_status == "mapped",
                    )
                )
                or 0
            )
            broker_count = int(await session.scalar(select(func.count(BrokerFlowDaily.id))) or 0)
            tradebook_count = int(
                await session.scalar(select(func.count(TradebookAggregate.id))) or 0
            )
            trade_count = int(await session.scalar(select(func.count(TradePrint.id))) or 0)
            orderbook_count = int(
                await session.scalar(select(func.count(OrderbookSnapshot.id))) or 0
            )
            return {
                "active_stocks": stock_count,
                "stocks_with_eod_history": history_count,
                "pluang_mapped_stocks": mapping_count,
                "broker_flow_rows": broker_count,
                "tradebook_aggregate_rows": tradebook_count,
                "trade_print_rows": trade_count,
                "orderbook_snapshots": orderbook_count,
            }

    @staticmethod
    async def _stock_id(session: AsyncSession, ticker: str) -> int:
        stock_id = await session.scalar(select(Stock.id).where(Stock.ticker == ticker.upper()))
        if stock_id is None:
            raise LookupError(f"stock {ticker.upper()} not found")
        return int(stock_id)


def _sanitize(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else _sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _is_synthetic_identity(value: str) -> bool:
    normalized = value.strip().upper()
    return normalized.startswith(("FIXTURE-", "SYNTHETIC-", "TEST-"))
