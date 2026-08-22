from decimal import Decimal

from app.providers.zapi import map_zapi_history, map_zapi_summary_row


def test_zapi_history_mapping_preserves_share_units() -> None:
    result = map_zapi_history(
        {
            "code": "BBCA",
            "name": "Bank Central Asia Tbk.",
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
