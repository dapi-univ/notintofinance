import os

import httpx
import pytest


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_WAREHOUSE_TESTS") != "1",
    reason="set RUN_LIVE_WAREHOUSE_TESTS=1 with the configured FastAPI server running",
)
def test_live_bbca_broker_accumulation_uses_configured_warehouse() -> None:
    response = httpx.get(
        "http://127.0.0.1:8000/stocks/BBCA/broker-accumulation",
        params={"from": "2026-08-07", "to": "2026-08-21"},
        timeout=30,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "BBCA"
    assert payload["gateway"] == "zapi"
    assert payload["source_provider"] == "pluang"
    assert payload["coverage"]["state"] == "partial"
    assert len(payload["coverage"]["expected_sessions"]) == 10
    assert len(payload["coverage"]["covered_sessions"]) == 9
    assert payload["coverage"]["missing_sessions"] == ["2026-08-11"]
    assert payload["brokers"]
