from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InstrumentMappingRecord(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,12}$")
    provider: str = "pluang"
    provider_instrument_id: str | None
    provider_ticker: str
    exchange: str = "IDX"
    mapping_status: str
    source: str = "pluang-description-by-code"


class BrokerFlowRecord(BaseModel):
    ticker: str
    trade_date_from: date
    trade_date_to: date
    broker_code: str = Field(min_length=1)
    broker_name: str | None = None
    side: str
    rank: int = Field(gt=0)
    lots: int = Field(ge=0)
    shares: int = Field(ge=0)
    value_idr: Decimal = Field(ge=0)
    average_price: Decimal = Field(ge=0)
    provider: str = "pluang"
    source_scope: str = "top_n"
    source_top_n: int | None = Field(default=10, gt=0)


class BrokerDirectoryRecord(BaseModel):
    broker_code: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    classification: str | None = None
    gateway: str = "zapi"
    source_provider: str = "pluang"
    source_observed_at: datetime


class TradePrintRecord(BaseModel):
    ticker: str
    provider_sequence: str = Field(min_length=1)
    trade_date: date
    executed_at: datetime
    price: Decimal = Field(gt=0)
    lots: int = Field(ge=0)
    shares: int = Field(ge=0)
    aggressor_action: str | None
    provider: str = "pluang"
    gateway_observed_at: datetime | None = None
    session_binding_method: str | None = None
    provider_session_asserted: bool = False


class OrderbookLevelRecord(BaseModel):
    side: str
    level_rank: int = Field(gt=0)
    price: Decimal = Field(gt=0)
    lots: int = Field(ge=0)


class OrderbookSnapshotRecord(BaseModel):
    ticker: str
    provider: str = "pluang"
    observed_at: datetime
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    levels: list[OrderbookLevelRecord]


class RunningTradesPage(BaseModel):
    records: list[TradePrintRecord]
    next_cursor: str | None


class TradebookAggregateRecord(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,12}$")
    trade_date: date
    view_type: str
    bucket_key: str = Field(min_length=1)
    price: Decimal | None = Field(default=None, gt=0)
    time_bucket: str | None = None
    buy_frequency: int | None = Field(default=None, ge=0)
    buy_lots: int | None = Field(default=None, ge=0)
    sell_frequency: int | None = Field(default=None, ge=0)
    sell_lots: int | None = Field(default=None, ge=0)
    pre_frequency: int | None = Field(default=None, ge=0)
    pre_lots: int | None = Field(default=None, ge=0)
    post_frequency: int | None = Field(default=None, ge=0)
    post_lots: int | None = Field(default=None, ge=0)
    total_frequency: int | None = Field(default=None, ge=0)
    total_lots: int | None = Field(default=None, ge=0)
    provider: str = "pluang"
    source_scope: str = "provider_aggregate"


class TradebookSessionRecord(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,12}$")
    trade_date: date
    price_available: bool
    time_available: bool
    volume_available: bool
    processed_successfully: bool
    gateway_observed_at: datetime
    session_binding_method: str = "confirmed_latest_eod"
    provider_session_asserted: bool = False
    provider: str = "pluang"


class IngestionCursorState(BaseModel):
    instrument_key: str
    session_date: date | None
    cursor_value: str | None
    high_water_mark: str | None
    status: str
    collection_filter: dict[str, object] = Field(default_factory=dict)
    collection_floor_idr: Decimal | None = Field(default=None, ge=0)
    rows_fetched: int = Field(default=0, ge=0)
    rows_retained: int = Field(default=0, ge=0)


class RawPayloadRecord(BaseModel):
    provider: str
    gateway: str
    source_provider: str
    dataset: str
    instrument_key: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    cursor_value: str | None = None
    payload: dict[str, object]
    normalization_status: str
    normalization_error: str | None = None


class MarketPriorityCandidate(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,12}$")
    latest_close: Decimal | None = Field(default=None, gt=0)
    listed_shares: int | None = Field(default=None, ge=0)
    value_idr: Decimal | None = Field(default=None, ge=0)
    frequency: int | None = Field(default=None, ge=0)
