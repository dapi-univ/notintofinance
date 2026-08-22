from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


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
    }
