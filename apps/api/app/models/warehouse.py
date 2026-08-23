from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.market import Base


class InstrumentProviderMapping(Base):
    __tablename__ = "instrument_provider_mappings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    provider_instrument_id: Mapped[str | None] = mapped_column(Text)
    provider_ticker: Mapped[str] = mapped_column(Text)
    exchange: Mapped[str] = mapped_column(Text)
    mapping_status: Mapped[str] = mapped_column(Text)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source: Mapped[str] = mapped_column(Text)


class ProviderRequestLedger(Base):
    __tablename__ = "provider_request_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(Text)
    endpoint_name: Mapped[str] = mapped_column(Text)
    request_fingerprint: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempt_number: Mapped[int] = mapped_column(Integer)
    quota_limit: Mapped[int | None] = mapped_column(Integer)
    quota_remaining_minute: Mapped[int | None] = mapped_column(Integer)
    quota_remaining_month: Mapped[int | None] = mapped_column(Integer)
    plan_expired: Mapped[bool | None] = mapped_column(Boolean)
    cache_status: Mapped[str | None] = mapped_column(Text)
    rows_received: Mapped[int | None] = mapped_column(Integer)
    error_class: Mapped[str | None] = mapped_column(Text)
    warning: Mapped[str | None] = mapped_column(Text)


class RawProviderPayload(Base):
    __tablename__ = "raw_provider_payloads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    gateway: Mapped[str] = mapped_column(Text)
    source_provider: Mapped[str] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(Text)
    instrument_key: Mapped[str | None] = mapped_column(Text)
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    cursor_value: Mapped[str | None] = mapped_column(Text)
    response_hash: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    normalization_status: Mapped[str] = mapped_column(Text)
    normalization_error: Mapped[str | None] = mapped_column(Text)


class BrokerFlowDaily(Base):
    __tablename__ = "broker_flow_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"))
    trade_date_from: Mapped[date] = mapped_column(Date)
    trade_date_to: Mapped[date] = mapped_column(Date)
    broker_code: Mapped[str] = mapped_column(Text)
    broker_name: Mapped[str | None] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer)
    lots: Mapped[int] = mapped_column(BigInteger)
    shares: Mapped[int] = mapped_column(BigInteger)
    value_idr: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    average_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    provider: Mapped[str] = mapped_column(Text)
    source_scope: Mapped[str] = mapped_column(Text)
    source_top_n: Mapped[int | None] = mapped_column(Integer)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TradebookAggregate(Base):
    __tablename__ = "tradebook_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "provider",
            "trade_date",
            "view_type",
            "bucket_key",
            name="tradebook_aggregates_identity_key",
        ),
        CheckConstraint(
            "view_type in ('price', 'time', 'volume')",
            name="tradebook_aggregates_view_check",
        ),
        CheckConstraint(
            "length(btrim(bucket_key)) > 0",
            name="tradebook_aggregates_bucket_not_blank",
        ),
        CheckConstraint(
            "price is null or price > 0",
            name="tradebook_aggregates_price_positive",
        ),
        CheckConstraint(
            "(buy_frequency is null or buy_frequency >= 0) "
            "and (buy_lots is null or buy_lots >= 0) "
            "and (sell_frequency is null or sell_frequency >= 0) "
            "and (sell_lots is null or sell_lots >= 0) "
            "and (pre_frequency is null or pre_frequency >= 0) "
            "and (pre_lots is null or pre_lots >= 0) "
            "and (post_frequency is null or post_frequency >= 0) "
            "and (post_lots is null or post_lots >= 0) "
            "and (total_frequency is null or total_frequency >= 0) "
            "and (total_lots is null or total_lots >= 0)",
            name="tradebook_aggregates_values_nonnegative",
        ),
        CheckConstraint(
            "source_scope = 'provider_aggregate'",
            name="tradebook_aggregates_scope_check",
        ),
        Index(
            "tradebook_aggregates_stock_date_idx",
            "stock_id",
            text("trade_date desc"),
            "view_type",
            "bucket_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    trade_date: Mapped[date] = mapped_column(Date)
    view_type: Mapped[str] = mapped_column(Text)
    bucket_key: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    time_bucket: Mapped[str | None] = mapped_column(Text)
    buy_frequency: Mapped[int | None] = mapped_column(BigInteger)
    buy_lots: Mapped[int | None] = mapped_column(BigInteger)
    sell_frequency: Mapped[int | None] = mapped_column(BigInteger)
    sell_lots: Mapped[int | None] = mapped_column(BigInteger)
    pre_frequency: Mapped[int | None] = mapped_column(BigInteger)
    pre_lots: Mapped[int | None] = mapped_column(BigInteger)
    post_frequency: Mapped[int | None] = mapped_column(BigInteger)
    post_lots: Mapped[int | None] = mapped_column(BigInteger)
    total_frequency: Mapped[int | None] = mapped_column(BigInteger)
    total_lots: Mapped[int | None] = mapped_column(BigInteger)
    source_scope: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TradePrint(Base):
    __tablename__ = "trade_prints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    provider_sequence: Mapped[str] = mapped_column(Text)
    trade_date: Mapped[date] = mapped_column(Date)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    lots: Mapped[int] = mapped_column(BigInteger)
    shares: Mapped[int] = mapped_column(BigInteger)
    aggressor_action: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderbookSnapshot(Base):
    __tablename__ = "orderbook_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    best_bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    best_ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    spread: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderbookLevel(Base):
    __tablename__ = "orderbook_levels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orderbook_snapshots.id", ondelete="CASCADE")
    )
    side: Mapped[str] = mapped_column(Text)
    level_rank: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    lots: Mapped[int] = mapped_column(BigInteger)


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(Text)
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE")
    )
    severity: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, object]] = mapped_column(JSONB)
    retryable: Mapped[bool] = mapped_column(Boolean)
    attempt_count: Mapped[int] = mapped_column(Integer)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_terminal: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionCursor(Base):
    __tablename__ = "ingestion_cursors"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "dataset",
            "instrument_key",
            "session_date",
            name="ingestion_cursors_identity_key",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "status in ('pending', 'running', 'partial', 'succeeded', 'failed', "
            "'exhausted', 'complete', 'blocked')",
            name="ingestion_cursors_status_check",
        ),
        CheckConstraint(
            "rows_fetched >= 0 and rows_retained >= 0 and rows_retained <= rows_fetched",
            name="ingestion_cursors_collection_counts_check",
        ),
        CheckConstraint(
            "collection_floor_idr is null or collection_floor_idr >= 0",
            name="ingestion_cursors_collection_floor_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    dataset: Mapped[str] = mapped_column(Text)
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE")
    )
    instrument_key: Mapped[str] = mapped_column(Text)
    session_date: Mapped[date | None] = mapped_column(Date)
    cursor_value: Mapped[str | None] = mapped_column(Text)
    high_water_mark: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    collection_filter: Mapped[dict[str, object]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    collection_floor_idr: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    rows_fetched: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    rows_retained: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
