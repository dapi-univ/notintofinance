import re
from datetime import date
from decimal import Decimal

import httpx

from app.schemas.domain import MarketBar, ProviderHistory, StockIdentity

TICKER_PATTERN = re.compile(r"^[A-Z0-9]{1,12}$")


class ZapiProvider:
    """Adapter for the documented Zapi/ZPI finance:idx endpoints."""

    name = "zapi"

    def __init__(self, api_key: str, base_url: str, client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def _get(self, endpoint: str, params: dict[str, str | int]) -> dict[str, object]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            response = await client.get(
                f"{self._base_url}/{endpoint}",
                params=params,
                headers={"x-api-key": self._api_key},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Zapi returned a non-object response")
            return payload
        finally:
            if owns_client:
                await client.aclose()

    async def get_stock_history(
        self,
        ticker: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 260,
    ) -> ProviderHistory:
        code = ticker.upper()
        if not TICKER_PATTERN.fullmatch(code):
            raise ValueError("invalid ticker")
        params: dict[str, str | int] = {"code": code, "length": min(limit, 2000)}
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["to"] = date_to.isoformat()
        return map_zapi_history(await self._get("stock-history", params))

    async def get_daily_market_summary(
        self, *, trade_date: date | None = None
    ) -> list[ProviderHistory]:
        params: dict[str, str | int] = {"length": 1000, "start": 0}
        if trade_date:
            params["date"] = trade_date.isoformat()
        payload = await self._get("stock-summary", params)
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            raise ValueError("Zapi stock-summary data must be a list")
        return [map_zapi_summary_row(row) for row in rows if isinstance(row, dict)]


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def map_zapi_history(payload: dict[str, object]) -> ProviderHistory:
    history = _unwrap_zapi_history(payload)
    code = str(history.get("code", "")).upper()
    name = str(history.get("name", code))
    items = history.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Zapi history items must be a list")
    bars = [
        MarketBar(
            trade_date=date.fromisoformat(str(item["date"])[:10]),
            open=_decimal(item["open"]),
            high=_decimal(item["high"]),
            low=_decimal(item["low"]),
            close=_decimal(item["close"]),
            previous=_decimal(item["previous"]),
            volume_shares=_int(item["volume"]),
            value_idr=_decimal(item["value"]),
            frequency=_int(item["frequency"]),
            foreign_buy_shares=_optional_int(item.get("foreignBuyShares")),
            foreign_sell_shares=_optional_int(item.get("foreignSellShares")),
            source="zapi",
        )
        for item in items
        if isinstance(item, dict)
    ]
    return ProviderHistory(stock=StockIdentity(ticker=code, company_name=name), bars=bars)


def _unwrap_zapi_history(payload: dict[str, object]) -> dict[str, object]:
    if "data" not in payload:
        return payload
    history = payload["data"]
    if not isinstance(history, dict):
        raise ValueError("Zapi stock-history data must be an object")
    unit = history.get("unit")
    if unit is not None and unit != "shares":
        raise ValueError("Zapi stock-history unit must be shares")
    return history


def map_zapi_summary_row(item: dict[str, object]) -> ProviderHistory:
    code = str(item.get("StockCode", "")).upper()
    bar = MarketBar(
        trade_date=date.fromisoformat(str(item["Date"])[:10]),
        open=_decimal(item["OpenPrice"]),
        high=_decimal(item["High"]),
        low=_decimal(item["Low"]),
        close=_decimal(item["Close"]),
        previous=_decimal(item["Previous"]),
        volume_shares=_int(item["Volume"]),
        value_idr=_decimal(item["Value"]),
        frequency=_int(item["Frequency"]),
        foreign_buy_shares=_optional_int(item.get("ForeignBuy")),
        foreign_sell_shares=_optional_int(item.get("ForeignSell")),
        non_regular_volume_shares=_optional_int(item.get("NonRegularVolume")),
        non_regular_value_idr=_optional_decimal(item.get("NonRegularValue")),
        non_regular_frequency=_optional_int(item.get("NonRegularFrequency")),
        source="zapi",
    )
    return ProviderHistory(
        stock=StockIdentity(ticker=code, company_name=str(item.get("StockName", code))),
        bars=[bar],
    )


def _optional_int(value: object) -> int | None:
    return None if value is None else _int(value)


def _int(value: object) -> int:
    return int(str(value))


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else _decimal(value)
