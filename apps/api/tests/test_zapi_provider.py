from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.zapi import (
    ZapiProvider,
    map_zapi_history,
    map_zapi_summary_row,
    map_zapi_universe_page,
)


def test_zapi_history_mapping_supports_direct_response_and_preserves_share_units() -> None:
    result = map_zapi_history(
        {
            "code": "BBCA",
            "name": "Bank Central Asia Tbk.",
            "unit": "shares",
            "items": [
                {
                    "date": "2026-08-21",
                    "open": 8000,
                    "high": 8200,
                    "low": 7950,
                    "close": 8150,
                    "previous": 8000,
                    "volume": 25_000_000,
                    "value": 203_750_000_000,
                    "frequency": 10_000,
                    "foreignBuyShares": 2_000_000,
                    "foreignSellShares": 1_500_000,
                }
            ],
        }
    )
    assert result.stock.ticker == "BBCA"
    assert result.bars[0].volume_shares == 25_000_000
    assert result.bars[0].close == Decimal("8150")


def test_zapi_history_mapping_supports_wrapped_live_response() -> None:
    result = map_zapi_history(
        {
            "data": {
                "code": "ANTM",
                "name": "Aneka Tambang Tbk.",
                "unit": "shares",
                "items": [
                    {
                        "date": "2026-08-21",
                        "open": 3000,
                        "high": 3200,
                        "low": 2980,
                        "close": 3150,
                        "previous": 3020,
                        "volume": 100_000_000,
                        "value": 315_000_000_000,
                        "frequency": 12_345,
                        "foreignBuyShares": 20_000_000,
                        "foreignSellShares": 18_000_000,
                    }
                ],
            },
            "project": "fixture-project",
            "timestamp": "2026-08-21T17:00:00Z",
        }
    )

    assert result.stock.ticker == "ANTM"
    assert result.bars[0].volume_shares == 100_000_000
    assert result.bars[0].foreign_buy_shares == 20_000_000


def test_zapi_history_mapping_rejects_malformed_envelope() -> None:
    with pytest.raises(ValueError, match="stock-history data must be an object"):
        map_zapi_history({"data": [], "project": "fixture-project"})


def test_zapi_history_mapping_rejects_envelope_without_data() -> None:
    with pytest.raises(ValueError, match="envelope is missing data"):
        map_zapi_history({"project": "fixture-project", "timestamp": "now"})


def test_zapi_history_mapping_rejects_wrapped_non_share_unit() -> None:
    with pytest.raises(ValueError, match="stock-history unit must be shares"):
        map_zapi_history({"data": {"unit": "lots"}})


def test_zapi_history_mapping_rejects_direct_non_share_unit() -> None:
    with pytest.raises(ValueError, match="stock-history unit must be shares"):
        map_zapi_history({"unit": "lots"})


def test_zapi_summary_maps_non_regular_fields() -> None:
    result = map_zapi_summary_row(
        {
            "Date": "2026-08-21T00:00:00",
            "StockCode": "ANTM",
            "StockName": "Aneka Tambang Tbk.",
            "OpenPrice": 3000,
            "High": 3200,
            "Low": 2980,
            "Close": 3150,
            "Previous": 3020,
            "Volume": 100_000_000,
            "Value": 315_000_000_000,
            "Frequency": 12_345,
            "ForeignBuy": 20_000_000,
            "ForeignSell": 18_000_000,
            "NonRegularVolume": 500,
            "NonRegularValue": 1_575_000,
            "NonRegularFrequency": 3,
        }
    )
    assert result.bars[0].non_regular_volume_shares == 500
    assert result.bars[0].source == "zapi"


@pytest.mark.parametrize("wrapped", [False, True])
def test_zapi_securities_normalization(wrapped: bool) -> None:
    body: dict[str, object] = {
        "data": [
            {
                "Code": "bbri",
                "Name": "Bank Rakyat Indonesia (Persero) Tbk.",
                "ListingBoard": "Utama",
            },
            {"Code": "TINS", "Name": ""},
        ],
        "dataset": "securities",
        "recordsFiltered": 2,
    }
    payload = {"project": "fixture", "data": body, "timestamp": "now"} if wrapped else body

    stocks, total = map_zapi_universe_page(payload)

    assert total == 2
    assert [stock.ticker for stock in stocks] == ["BBRI", "TINS"]
    assert stocks[0].company_name == "Bank Rakyat Indonesia (Persero) Tbk."
    assert stocks[1].company_name == "TINS"


def test_zapi_securities_rejects_malformed_envelope() -> None:
    with pytest.raises(ValueError, match="envelope is missing data"):
        map_zapi_universe_page({"project": "fixture", "timestamp": "now"})


def test_zapi_history_omits_invalid_zero_price_rows_and_reports_them() -> None:
    payload = {
        "code": "TINS",
        "name": "TIMAH Tbk.",
        "unit": "shares",
        "items": [
            {
                "date": "2026-08-21",
                "open": 1000,
                "high": 1050,
                "low": 990,
                "close": 1020,
                "previous": 1000,
                "volume": 100,
                "value": 102000,
                "frequency": 10,
            },
            {
                "date": "2026-08-20",
                "open": 0,
                "high": 0,
                "low": 0,
                "close": 0,
                "previous": 0,
                "volume": 0,
                "value": 0,
                "frequency": 0,
            },
        ],
    }

    result = map_zapi_history(payload)

    assert len(result.bars) == 1
    assert result.rejected_items == 1


async def test_zapi_retries_transient_failures_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={"code": "BBCA", "name": "Bank Central Asia Tbk.", "items": []},
        )

    sleep = AsyncMock()
    monkeypatch.setattr("app.providers.zapi.asyncio.sleep", sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ZapiProvider(
            "fixture-key",
            "https://provider.invalid",
            client,
            max_retries=1,
        )
        result = await provider.get_stock_history("BBCA", limit=2)

    assert result.stock.ticker == "BBCA"
    assert attempts == 2
    sleep.assert_awaited_once()
