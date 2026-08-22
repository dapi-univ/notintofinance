from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StockIdentity(BaseModel):
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,12}$")
    company_name: str = Field(min_length=1)
    sector: str | None = None
    subsector: str | None = None


class MarketBar(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    trade_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    previous: Decimal = Field(gt=0)
    volume_shares: int = Field(ge=0)
    value_idr: Decimal = Field(ge=0)
    frequency: int = Field(ge=0)
    foreign_buy_shares: int | None = Field(default=None, ge=0)
    foreign_sell_shares: int | None = Field(default=None, ge=0)
    non_regular_volume_shares: int | None = Field(default=None, ge=0)
    non_regular_value_idr: Decimal | None = Field(default=None, ge=0)
    non_regular_frequency: int | None = Field(default=None, ge=0)
    source: str = Field(min_length=1)
    ingested_at: datetime | None = None

    @model_validator(mode="after")
    def validate_ohlc(self) -> "MarketBar":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be at least open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be at most open, close, and high")
        return self


class ProviderHistory(BaseModel):
    stock: StockIdentity
    bars: list[MarketBar]
