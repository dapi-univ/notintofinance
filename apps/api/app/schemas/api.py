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


class BrokerFlowItemResponse(BaseModel):
    trade_date_from: date
    trade_date_to: date
    broker_code: str
    broker_name: str | None
    side: str
    rank: int
    lots: int
    shares: int
    value_idr: Decimal
    average_price: Decimal
    provider: str
    source_scope: str
    source_top_n: int | None


class BrokerFlowResponse(BaseModel):
    ticker: str
    source_scope: str
    source_top_n: int | None
    rows: list[BrokerFlowItemResponse]


class TradePrintResponse(BaseModel):
    id: int
    provider_sequence: str
    trade_date: date
    executed_at: datetime
    price: Decimal
    lots: int
    shares: int
    aggressor_action: str | None
    provider: str


class TradesResponse(BaseModel):
    ticker: str
    rows: list[TradePrintResponse]
    next_cursor: int | None


class OrderbookLevelResponse(BaseModel):
    side: str
    level_rank: int
    price: Decimal
    lots: int


class OrderbookSnapshotResponse(BaseModel):
    ticker: str
    kind: str = "resting_liquidity_snapshot"
    provider: str
    observed_at: datetime
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    levels: list[OrderbookLevelResponse]


class CoverageResponse(BaseModel):
    active_stocks: int
    stocks_with_eod_history: int
    pluang_mapped_stocks: int
    broker_flow_rows: int
    trade_print_rows: int
    orderbook_snapshots: int


class ProviderQuotaResponse(BaseModel):
    provider: str
    observed_at: datetime | None
    requests_today: int
    limit: int | None
    remaining_minute: int | None
    remaining_month: int | None
    plan_expired: bool | None
    warning: str | None


class QuotaStatusResponse(BaseModel):
    providers: list[ProviderQuotaResponse]
