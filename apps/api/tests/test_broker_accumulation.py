from datetime import date, datetime
from decimal import Decimal

from app.analytics.broker_accumulation import build_broker_accumulation
from app.models.warehouse import BrokerDirectory, BrokerFlowDaily


def _flow(session: date, side: str, value: str, *, rank: int = 1) -> BrokerFlowDaily:
    return BrokerFlowDaily(
        stock_id=1,
        trade_date_from=session,
        trade_date_to=session,
        broker_code="AK",
        side=side,
        rank=rank,
        lots=10,
        shares=1000,
        value_idr=Decimal(value),
        average_price=Decimal("6450"),
        provider="pluang",
        source_scope="top_n",
        source_top_n=10,
    )


def test_missing_side_remains_explicit_and_cumulative_window_is_deterministic() -> None:
    first = date(2026, 8, 20)
    second = date(2026, 8, 21)
    directory = BrokerDirectory(
        broker_code="AK",
        broker_name="Verified Broker",
        classification="FOREIGN",
        gateway="zapi",
        source_provider="pluang",
        source_observed_at=datetime.fromisoformat("2026-08-23T07:01:33+00:00"),
    )

    result = build_broker_accumulation(
        ticker="BBCA",
        date_from=first,
        date_to=second,
        expected_sessions=[first, second],
        rows=[(_flow(first, "BUY", "1000"), directory), (_flow(second, "SELL", "400"), directory)],
    )

    broker = result.brokers[0]
    assert broker.broker_name == "Verified Broker"
    assert broker.classification == "FOREIGN"
    assert broker.observed_top_n_net_value == Decimal("600")
    assert broker.buy_appearances == broker.sell_appearances == 1
    assert broker.daily[0].buy_observed is True
    assert broker.daily[0].sell_observed is False
    assert broker.daily[1].cumulative_observed_top_n_net_value == Decimal("600")
    assert result.coverage.state == "complete"


def test_missing_sessions_are_reported_as_partial_not_zero_activity() -> None:
    first = date(2026, 8, 20)
    second = date(2026, 8, 21)

    result = build_broker_accumulation(
        ticker="BBCA",
        date_from=first,
        date_to=second,
        expected_sessions=[first, second],
        rows=[(_flow(first, "BUY", "1000"), None)],
    )

    assert result.coverage.state == "partial"
    assert result.coverage.missing_sessions == [second]
    assert result.brokers[0].daily[1].buy_observed is False
    assert result.brokers[0].daily[1].sell_observed is False
