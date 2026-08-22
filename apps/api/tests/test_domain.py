from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.domain import MarketBar


def test_invalid_ohlc_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MarketBar(
            trade_date=date(2026, 8, 21),
            open=100,
            high=90,
            low=80,
            close=95,
            previous=98,
            volume_shares=1000,
            value_idr=95_000,
            frequency=12,
            source="test",
        )
