from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticker: Mapped[str] = mapped_column(Text, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    subsector: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyMarketData(Base):
    __tablename__ = "daily_market_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    previous: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume_shares: Mapped[int] = mapped_column(BigInteger)
    value_idr: Mapped[Decimal] = mapped_column(Numeric(24, 2))
    frequency: Mapped[int] = mapped_column(BigInteger)
    foreign_buy_shares: Mapped[int | None] = mapped_column(BigInteger)
    foreign_sell_shares: Mapped[int | None] = mapped_column(BigInteger)
    non_regular_volume_shares: Mapped[int | None] = mapped_column(BigInteger)
    non_regular_value_idr: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    non_regular_frequency: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    requested_date: Mapped[date | None] = mapped_column(Date)
    rows_received: Mapped[int] = mapped_column(default=0)
    rows_inserted: Mapped[int] = mapped_column(default=0)
    rows_updated: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
