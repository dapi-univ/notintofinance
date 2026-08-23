import asyncio
import random
import re
from datetime import date
from decimal import Decimal

import httpx

from app.schemas.domain import MarketBar, ProviderHistory, ProviderUniverse, StockIdentity

TICKER_PATTERN = re.compile(r"^[A-Z0-9]{1,12}$")


class ZapiProvider:
    """Adapter for the documented Zapi/ZPI finance:idx endpoints."""

    name = "zapi"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        *,
        max_retries: int = 2,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._max_retries = max_retries

    async def _get(self, endpoint: str, params: dict[str, str | int]) -> dict[str, object]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30)
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.get(
                        f"{self._base_url}/{endpoint}",
                        params=params,
                        headers={"x-api-key": self._api_key},
                    )
                    if (
                        response.status_code == 429 or response.status_code >= 500
                    ) and attempt < self._max_retries:
                        await asyncio.sleep(_retry_delay(response, attempt))
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("Zapi returned a non-object response")
                    return payload
                except httpx.RequestError:
                    if attempt >= self._max_retries:
                        raise
                    await asyncio.sleep(_backoff_delay(attempt))
            raise RuntimeError("Zapi request retry loop exhausted")
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
        rows = _unwrap_rows(payload, dataset="stock-summary")
        return [map_zapi_summary_row(row) for row in rows if isinstance(row, dict)]

    async def get_stock_universe(self) -> ProviderUniverse:
        page_size = 1000
        start = 0
        stocks: dict[str, StockIdentity] = {}
        expected_total: int | None = None
        while expected_total is None or start < expected_total:
            payload = await self._get("securities", {"start": start, "length": page_size})
            page, total = map_zapi_universe_page(payload)
            expected_total = total
            for stock in page:
                stocks[stock.ticker] = stock
            if not page:
                break
            start += len(page)
        if expected_total is None or len(stocks) != expected_total:
            raise ValueError(
                "Zapi securities pagination incomplete: "
                f"expected {expected_total}, got {len(stocks)}"
            )
        return ProviderUniverse(stocks=list(stocks.values()), total=expected_total)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def map_zapi_history(payload: dict[str, object]) -> ProviderHistory:
    history = _unwrap_zapi_history(payload)
    code = str(history.get("code", "")).upper()
    name = str(history.get("name", code))
    items = history.get("items", [])
    if not isinstance(items, list):
        raise ValueError("Zapi history items must be a list")
    bars_by_date: dict[date, MarketBar] = {}
    rejected = 0
    for item in items:
        if not isinstance(item, dict):
            rejected += 1
            continue
        try:
            bar = MarketBar(
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
        except (KeyError, TypeError, ValueError):
            rejected += 1
            continue
        if bar.trade_date in bars_by_date:
            rejected += 1
        bars_by_date[bar.trade_date] = bar
    bars = sorted(bars_by_date.values(), key=lambda bar: bar.trade_date)
    if items and not bars:
        raise ValueError("Zapi stock-history contains no valid market bars")
    return ProviderHistory(
        stock=StockIdentity(ticker=code, company_name=name),
        bars=bars,
        rejected_items=rejected,
    )


def _unwrap_zapi_history(payload: dict[str, object]) -> dict[str, object]:
    history = payload
    if "data" in payload:
        wrapped = payload["data"]
        if isinstance(wrapped, dict):
            history = wrapped
        elif "project" in payload or "timestamp" in payload:
            raise ValueError("Zapi stock-history data must be an object")
    elif "project" in payload or "timestamp" in payload:
        raise ValueError("Zapi stock-history envelope is missing data")
    unit = history.get("unit")
    if unit is not None and unit != "shares":
        raise ValueError("Zapi stock-history unit must be shares")
    return history


def map_zapi_universe_page(
    payload: dict[str, object],
) -> tuple[list[StockIdentity], int]:
    body = _unwrap_dataset(payload, dataset="securities")
    rows = body.get("data")
    if not isinstance(rows, list):
        raise ValueError("Zapi securities data must be a list")
    total = body.get("recordsFiltered", body.get("recordsTotal"))
    if not isinstance(total, int) or total < 0:
        raise ValueError("Zapi securities response must include a valid record count")
    stocks: list[StockIdentity] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Zapi securities row must be an object")
        ticker = str(row.get("Code", "")).strip().upper()
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("Zapi securities row contains an invalid ticker")
        name = str(row.get("Name", "")).strip() or ticker
        stocks.append(StockIdentity(ticker=ticker, company_name=name))
    return stocks, total


def _unwrap_dataset(payload: dict[str, object], *, dataset: str) -> dict[str, object]:
    body = payload
    if "data" in payload and isinstance(payload["data"], dict):
        body = payload["data"]
    elif ("project" in payload or "timestamp" in payload) and "data" not in payload:
        raise ValueError(f"Zapi {dataset} envelope is missing data")
    actual_dataset = body.get("dataset")
    if actual_dataset is not None and actual_dataset != dataset:
        raise ValueError(f"Zapi response dataset must be {dataset}")
    return body


def _unwrap_rows(payload: dict[str, object], *, dataset: str) -> list[object]:
    body = _unwrap_dataset(payload, dataset=dataset)
    rows = body.get("data", [])
    if not isinstance(rows, list):
        raise ValueError(f"Zapi {dataset} data must be a list")
    return rows


def _backoff_delay(attempt: int) -> float:
    return 0.2 * (2**attempt) + random.uniform(0, 0.1)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 0)
        except ValueError:
            pass
    return _backoff_delay(attempt)


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
