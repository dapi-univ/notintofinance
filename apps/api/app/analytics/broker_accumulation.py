from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.warehouse import BrokerDirectory, BrokerFlowDaily
from app.schemas.api import (
    BrokerAccumulationBrokerResponse,
    BrokerAccumulationCoverageResponse,
    BrokerAccumulationPointResponse,
    BrokerAccumulationResponse,
)


@dataclass
class _Side:
    value: Decimal = Decimal(0)
    lots: int = 0
    shares: int = 0
    observed: bool = False
    rank: int | None = None


@dataclass
class _Broker:
    name: str | None = None
    classification: str | None = None
    daily: dict[date, dict[str, _Side]] = field(default_factory=dict)


def build_broker_accumulation(
    *,
    ticker: str,
    date_from: date,
    date_to: date,
    expected_sessions: Sequence[date],
    rows: Sequence[tuple[BrokerFlowDaily, BrokerDirectory | None]],
) -> BrokerAccumulationResponse:
    brokers: dict[str, _Broker] = {}
    covered_sessions: set[date] = set()
    for flow, directory in rows:
        covered_sessions.add(flow.trade_date_to)
        broker = brokers.setdefault(
            flow.broker_code,
            _Broker(
                name=directory.broker_name if directory else flow.broker_name,
                classification=directory.classification if directory else None,
            ),
        )
        sides = broker.daily.setdefault(
            flow.trade_date_to, {"BUY": _Side(), "SELL": _Side()}
        )
        side = sides[flow.side]
        side.value += flow.value_idr
        side.lots += flow.lots
        side.shares += flow.shares
        side.observed = True
        side.rank = flow.rank

    ranked: list[BrokerAccumulationBrokerResponse] = []
    for code, broker in brokers.items():
        buy_value = sell_value = Decimal(0)
        buy_lots = sell_lots = buy_shares = sell_shares = 0
        buy_appearances = sell_appearances = 0
        latest_buy_rank: int | None = None
        latest_sell_rank: int | None = None
        cumulative_value = Decimal(0)
        cumulative_lots = cumulative_shares = 0
        points: list[BrokerAccumulationPointResponse] = []
        for session in expected_sessions:
            sides = broker.daily.get(session, {"BUY": _Side(), "SELL": _Side()})
            buy = sides["BUY"]
            sell = sides["SELL"]
            buy_value += buy.value
            sell_value += sell.value
            buy_lots += buy.lots
            sell_lots += sell.lots
            buy_shares += buy.shares
            sell_shares += sell.shares
            buy_appearances += int(buy.observed)
            sell_appearances += int(sell.observed)
            if buy.observed:
                latest_buy_rank = buy.rank
            if sell.observed:
                latest_sell_rank = sell.rank
            net_value = buy.value - sell.value
            net_lots = buy.lots - sell.lots
            net_shares = buy.shares - sell.shares
            cumulative_value += net_value
            cumulative_lots += net_lots
            cumulative_shares += net_shares
            points.append(
                BrokerAccumulationPointResponse(
                    trade_date=session,
                    buy_observed=buy.observed,
                    sell_observed=sell.observed,
                    observed_top_n_buy_value=buy.value,
                    observed_top_n_sell_value=sell.value,
                    observed_top_n_net_value=net_value,
                    cumulative_observed_top_n_net_value=cumulative_value,
                    observed_top_n_buy_lots=buy.lots,
                    observed_top_n_sell_lots=sell.lots,
                    observed_top_n_net_lots=net_lots,
                    cumulative_observed_top_n_net_lots=cumulative_lots,
                    observed_top_n_buy_shares=buy.shares,
                    observed_top_n_sell_shares=sell.shares,
                    observed_top_n_net_shares=net_shares,
                    cumulative_observed_top_n_net_shares=cumulative_shares,
                )
            )
        ranked.append(
            BrokerAccumulationBrokerResponse(
                broker_code=code,
                broker_name=broker.name,
                classification=broker.classification,
                observed_top_n_buy_value=buy_value,
                observed_top_n_sell_value=sell_value,
                observed_top_n_net_value=buy_value - sell_value,
                observed_top_n_buy_lots=buy_lots,
                observed_top_n_sell_lots=sell_lots,
                observed_top_n_net_lots=buy_lots - sell_lots,
                observed_top_n_buy_shares=buy_shares,
                observed_top_n_sell_shares=sell_shares,
                observed_top_n_net_shares=buy_shares - sell_shares,
                buy_appearances=buy_appearances,
                sell_appearances=sell_appearances,
                latest_buy_rank=latest_buy_rank,
                latest_sell_rank=latest_sell_rank,
                daily=points,
            )
        )

    ranked.sort(
        key=lambda item: (-abs(item.observed_top_n_net_value), item.broker_code)
    )
    expected = list(expected_sessions)
    covered = [session for session in expected if session in covered_sessions]
    missing = [session for session in expected if session not in covered_sessions]
    state = "unavailable" if not covered else "complete" if not missing else "partial"
    return BrokerAccumulationResponse(
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
        coverage=BrokerAccumulationCoverageResponse(
            expected_sessions=expected,
            covered_sessions=covered,
            missing_sessions=missing,
            state=state,
        ),
        brokers=ranked,
    )
