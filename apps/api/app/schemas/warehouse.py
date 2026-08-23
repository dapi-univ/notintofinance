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


class IngestionCursorState(BaseModel):
    instrument_key: str
    session_date: date | None
    cursor_value: str | None
    high_water_mark: str | None
    status: str


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
