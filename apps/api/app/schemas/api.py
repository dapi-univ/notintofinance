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


class BrokerAccumulationCoverageResponse(BaseModel):
    expected_sessions: list[date]
    covered_sessions: list[date]
    missing_sessions: list[date]
    state: str


class BrokerAccumulationPointResponse(BaseModel):
    trade_date: date
    buy_observed: bool
    sell_observed: bool
    observed_top_n_buy_value: Decimal
    observed_top_n_sell_value: Decimal
    observed_top_n_net_value: Decimal
    cumulative_observed_top_n_net_value: Decimal
    observed_top_n_buy_lots: int
    observed_top_n_sell_lots: int
    observed_top_n_net_lots: int
    cumulative_observed_top_n_net_lots: int
    observed_top_n_buy_shares: int
    observed_top_n_sell_shares: int
    observed_top_n_net_shares: int
    cumulative_observed_top_n_net_shares: int


class BrokerAccumulationBrokerResponse(BaseModel):
    broker_code: str
    broker_name: str | None
    classification: str | None
    observed_top_n_buy_value: Decimal
    observed_top_n_sell_value: Decimal
    observed_top_n_net_value: Decimal
    observed_top_n_buy_lots: int
    observed_top_n_sell_lots: int
    observed_top_n_net_lots: int
    observed_top_n_buy_shares: int
    observed_top_n_sell_shares: int
    observed_top_n_net_shares: int
    buy_appearances: int
    sell_appearances: int
    latest_buy_rank: int | None
    latest_sell_rank: int | None
    daily: list[BrokerAccumulationPointResponse]


class BrokerAccumulationResponse(BaseModel):
    ticker: str
    date_from: date = Field(serialization_alias="from")
    date_to: date = Field(serialization_alias="to")
    source_scope: str = "top_n"
    source_top_n: int = 10
    coverage_note: str = "TOP-10 OBSERVED · NOT FULL MARKET"
    gateway: str = "zapi"
    source_provider: str = "pluang"
    coverage: BrokerAccumulationCoverageResponse
    brokers: list[BrokerAccumulationBrokerResponse]


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
    next_cursor: str | None


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
    tradebook_aggregate_rows: int
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
