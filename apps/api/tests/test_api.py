from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.trade_cursor import InvalidTradeCursor


class FakeWarehouseService:
    async def broker_flow(
        self, ticker: str, date_from: object, date_to: object
    ) -> dict[str, object]:
        return {"ticker": ticker, "source_scope": "top_n", "source_top_n": 10, "rows": []}

    async def trades(
        self,
        ticker: str,
        date_from: object,
        date_to: object,
        *,
        limit: int,
        cursor: str | None,
    ) -> dict[str, object]:
        if cursor:
            raise InvalidTradeCursor("invalid or incompatible trade cursor")
        return {"ticker": ticker, "rows": [], "next_cursor": None}

    async def latest_orderbook(self, ticker: str) -> dict[str, object]:
        return {
            "ticker": ticker,
            "kind": "resting_liquidity_snapshot",
            "provider": "pluang",
            "observed_at": "2026-08-23T07:01:33Z",
            "best_bid": 6425,
            "best_ask": 6450,
            "spread": 25,
            "levels": [],
        }

    async def coverage(self) -> dict[str, int]:
        return {
            "active_stocks": 962,
            "stocks_with_eod_history": 439,
            "pluang_mapped_stocks": 3,
            "broker_flow_rows": 60,
            "trade_print_rows": 100,
            "orderbook_snapshots": 3,
        }

    async def quota_status(self) -> dict[str, object]:
        return {"providers": []}


def test_dashboard_api_data_flow() -> None:
    app = create_app(
        Settings(
            market_data_provider="mock",
            database_url=None,
            cors_origins="http://localhost:3000",
        )
    )
    with TestClient(app) as client:
        health = client.get("/health")
        stocks = client.get("/stocks")
        history = client.get("/stocks/BBCA/history")
        status = client.get("/data/status")

    assert health.json() == {"status": "ok"}
    assert len(stocks.json()) >= 2
    assert history.status_code == 200
    assert history.json()["ticker"] == "BBCA"
    assert history.json()["bars"][0]["frequency_analyzer_raw_shares"] is not None
    assert status.json()["is_mock"] is True
    assert status.json()["last_successful_ingestion"]["status"] == "succeeded"


def test_unknown_ticker_returns_404() -> None:
    app = create_app(Settings(market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        response = client.get("/stocks/ZZZZ/history")
    assert response.status_code == 404


def test_history_timeframes_are_bounded_or_return_all_available_data() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        one_month = client.get("/stocks/BBCA/history?timeframe=1M")
        all_history = client.get("/stocks/BBCA/history?timeframe=ALL")

    assert one_month.status_code == 200
    assert all_history.status_code == 200
    assert 0 < len(one_month.json()["bars"]) < len(all_history.json()["bars"])
    assert len(all_history.json()["bars"]) == 260
    assert one_month.json()["bars"][0]["date"] >= "2026-07-21"
    assert one_month.json()["bars"][-1]["date"] == all_history.json()["bars"][-1]["date"]
    assert set(all_history.json()["bars"][0]) >= {
        "open",
        "high",
        "low",
        "close",
        "volume_shares",
        "frequency",
        "frequency_analyzer_raw_shares",
        "foreign_buy_shares",
        "foreign_sell_shares",
        "foreign_net_shares",
        "cumulative_foreign_net_shares",
    }


def test_stock_search_filters_active_universe() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        response = client.get("/stocks?q=telkom&limit=10")

    assert response.status_code == 200
    assert [stock["ticker"] for stock in response.json()] == ["TLKM"]


def test_foreign_net_and_cumulative_values_are_derived_from_stored_shares() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        response = client.get("/stocks/BBCA/history?timeframe=1M")

    bars = response.json()["bars"]
    running = 0
    for bar in bars:
        expected_net = bar["foreign_buy_shares"] - bar["foreign_sell_shares"]
        running += expected_net
        assert bar["foreign_net_shares"] == expected_net
        assert bar["cumulative_foreign_net_shares"] == running


def test_database_only_warehouse_read_routes_and_coverage_contracts() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        app.state.warehouse_service = FakeWarehouseService()
        broker = client.get("/stocks/BBCA/broker-flow?from=2026-08-21&to=2026-08-21")
        trades = client.get("/stocks/BBCA/trades?from=2026-08-21&to=2026-08-21&limit=100")
        orderbook = client.get("/stocks/BBCA/orderbook/latest")
        coverage = client.get("/data/coverage")
        quota = client.get("/data/quota-status")

    assert broker.status_code == 200
    assert broker.json()["source_top_n"] == 10
    assert trades.status_code == 200
    assert orderbook.json()["kind"] == "resting_liquidity_snapshot"
    assert coverage.json()["active_stocks"] == 962
    assert quota.json() == {"providers": []}


def test_warehouse_routes_enforce_bounded_ranges() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        app.state.warehouse_service = FakeWarehouseService()
        broker = client.get("/stocks/BBCA/broker-flow?from=2026-01-01&to=2026-08-21")
        trades = client.get("/stocks/BBCA/trades?from=2026-08-01&to=2026-08-21")

    assert broker.status_code == 422
    assert trades.status_code == 422


def test_trade_route_rejects_malformed_opaque_cursor() -> None:
    app = create_app(Settings(app_env="test", market_data_provider="mock", database_url=None))
    with TestClient(app) as client:
        app.state.warehouse_service = FakeWarehouseService()
        response = client.get(
            "/stocks/BBCA/trades?from=2026-08-21&to=2026-08-21&cursor=invalid"
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid or incompatible trade cursor"
