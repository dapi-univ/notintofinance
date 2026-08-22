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
