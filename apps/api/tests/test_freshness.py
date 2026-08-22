from datetime import date

from app.services.market import expected_latest_trade_date


def test_weekend_uses_previous_friday() -> None:
    assert expected_latest_trade_date(date(2026, 8, 23)) == date(2026, 8, 21)
