from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StockListItemResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None
    subsector: str | None
    latest_close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    latest_trade_date: date | None
    sparkline: list[Decimal]
    has_history: bool


class StockDetailResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None
    subsector: str | None


class HistoryBarResponse(BaseModel):
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    previous: Decimal
    volume_shares: int
    volume_lots: Decimal
    value_idr: Decimal
    frequency: int
    frequency_analyzer_raw_shares: Decimal | None
    frequency_analyzer_raw_lots: Decimal | None
    foreign_buy_shares: int | None
    foreign_sell_shares: int | None
    foreign_net_shares: int | None
    cumulative_foreign_net_shares: int | None


class HistoryResponse(BaseModel):
    ticker: str
    company_name: str
    date_from: date | None = Field(serialization_alias="from")
    date_to: date | None = Field(serialization_alias="to")
    latest_trade_date: date | None
    is_stale: bool
    is_mock: bool
    source: str
    bars: list[HistoryBarResponse]


class IngestionStatusResponse(BaseModel):
    provider: str
    status: str
    finished_at: datetime | None
    rows_received: int


class DataStatusResponse(BaseModel):
    latest_trade_date: date | None
    expected_trade_date: date
    is_stale: bool
    is_mock: bool
    provider: str
    repository: str
    ingestion: IngestionStatusResponse | None
    last_successful_ingestion: IngestionStatusResponse | None
