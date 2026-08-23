import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.providers.pluang import (
    PluangProvider,
    map_pluang_broker_summary,
    map_pluang_orderbook,
    map_pluang_running_trades,
)

FIXTURES = Path(__file__).parent / "fixtures"
ZAPI_BASE_URL = "https://api.zpi.web.id/v1/finance:pluang"


def _fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_broker_buyers_and_sellers_preserve_capped_top_n_and_units() -> None:
    rows = map_pluang_broker_summary(_fixture("pluang_broker_summary.json"), "BBCA")

    assert [(row.side, row.broker_code) for row in rows] == [("BUY", "AK"), ("SELL", "RX")]
    assert all(row.source_scope == "top_n" for row in rows)
    assert all(row.source_top_n == 10 for row in rows)
    assert all(row.provider == "pluang" for row in rows)
    assert all(row.shares == row.lots * 100 for row in rows)


def test_running_trades_maps_sequence_action_lots_and_next_cursor() -> None:
    page = map_pluang_running_trades(
        _fixture("pluang_running_trades.json"), "BBCA", date(2026, 8, 21)
    )

    assert page.next_cursor == "MjI2OTQ="
    assert page.records[0].provider_sequence == "23034"
    assert page.records[0].lots == 29
    assert page.records[0].shares == 2900
    assert page.records[0].executed_at.utcoffset().total_seconds() == 7 * 3600
    assert page.records[0].aggressor_action == "SELL"


def test_running_trades_rejects_duplicate_provider_sequences() -> None:
    payload = _fixture("pluang_running_trades.json")
    body = payload["data"]
    assert isinstance(body, dict)
    rows = body["items"]
    assert isinstance(rows, list)
    rows[1] = rows[0]

    with pytest.raises(ValueError, match="duplicate"):
        map_pluang_running_trades(payload, "BBCA", date(2026, 8, 21))


def test_orderbook_maps_normalized_bid_and_ask_levels() -> None:
    snapshot = map_pluang_orderbook(_fixture("pluang_orderbook.json"), "BBCA")

    assert snapshot.best_bid == 6425
    assert snapshot.best_ask == 6450
    assert snapshot.spread == 25
    assert [(level.side, level.lots) for level in snapshot.levels] == [
        ("BID", 10955),
        ("ASK", 75223),
    ]


@pytest.mark.parametrize("fixture", ["pluang_mapping.json", "pluang_orderbook.json"])
def test_zapi_finance_pluang_fixtures_use_wrapped_envelope(fixture: str) -> None:
    payload = _fixture(fixture)

    assert payload["project"] == "finance:pluang"
    assert isinstance(payload["data"], dict)
    assert payload["data"]["source"] == "pluang"  # type: ignore[index]


def test_direct_upstream_shape_is_not_accepted_as_zapi_envelope() -> None:
    payload = _fixture("pluang_orderbook.json")
    body = payload["data"]
    assert isinstance(body, dict)

    with pytest.raises(ValueError, match="data must be an object"):
        map_pluang_orderbook(body, "BBCA")


async def test_provider_uses_ticker_zapi_key_and_no_browser_headers() -> None:
    transport = AsyncMock()
    transport.get_json.return_value = _fixture("pluang_broker_summary.json")
    provider = PluangProvider("fixture-key", ZAPI_BASE_URL, transport)

    rows, _ = await provider.get_broker_summary("BBCA", date(2026, 8, 21))

    assert rows[0].provider == "pluang"
    request = transport.get_json.await_args.kwargs
    assert request["url"] == f"{ZAPI_BASE_URL}/broker-summary"
    assert request["params"] == {
        "code": "BBCA",
        "startDate": "2026-08-21",
        "endDate": "2026-08-21",
        "net": "true",
    }
    assert request["headers"] == {"x-api-key": "fixture-key"}
    assert request["endpoint_name"] == "finance:pluang/broker-summary"


async def test_every_finance_pluang_endpoint_uses_the_server_zapi_key() -> None:
    transport = AsyncMock()
    transport.get_json.side_effect = [
        _fixture("pluang_mapping.json"),
        _fixture("pluang_broker_summary.json"),
        _fixture("pluang_running_trades.json"),
        _fixture("pluang_orderbook.json"),
    ]
    provider = PluangProvider("fixture-key", ZAPI_BASE_URL, transport)

    await provider.resolve_instrument("BBCA")
    await provider.get_broker_summary("BBCA", date(2026, 8, 21))
    await provider.get_running_trades("BBCA", date(2026, 8, 21))
    await provider.get_orderbook("BBCA")

    assert provider.name == "pluang"
    assert provider.gateway == "zapi"
    assert transport.get_json.await_count == 4
    for request in transport.get_json.await_args_list:
        assert request.kwargs["headers"] == {"x-api-key": "fixture-key"}
        assert request.kwargs["url"].startswith(ZAPI_BASE_URL)


async def test_canonical_ticker_orderbook_call_needs_no_mapping() -> None:
    transport = AsyncMock()
    transport.get_json.return_value = _fixture("pluang_orderbook.json")
    provider = PluangProvider("fixture-key", ZAPI_BASE_URL, transport)

    await provider.get_orderbook("bbca")

    assert transport.get_json.await_args.kwargs["params"] == {"code": "BBCA"}


async def test_raw_staging_identifies_zapi_gateway_and_pluang_source() -> None:
    transport = AsyncMock()
    transport.get_json.return_value = _fixture("pluang_mapping.json")
    sink = AsyncMock()
    provider = PluangProvider(
        "fixture-key", ZAPI_BASE_URL, transport, raw_payload_sink=sink
    )

    mapping = await provider.resolve_instrument("BBCA")

    assert mapping.provider_instrument_id == "10020"
    staged = sink.await_args.args[0]
    assert staged.provider == "pluang"
    assert staged.gateway == "zapi"
    assert staged.source_provider == "pluang"
    assert staged.dataset == "finance:pluang/resolve"
    assert staged.normalization_status == "normalized"


async def test_provider_stages_rejected_normalized_envelope() -> None:
    payload = _fixture("pluang_orderbook.json")
    body = payload["data"]
    assert isinstance(body, dict)
    body["bids"] = [{"price": 0, "lots": 1}]
    transport = AsyncMock()
    transport.get_json.return_value = payload
    sink = AsyncMock()
    provider = PluangProvider(
        "fixture-key", ZAPI_BASE_URL, transport, raw_payload_sink=sink
    )

    with pytest.raises(ValueError):
        await provider.get_orderbook("BBCA")

    staged = sink.await_args.args[0]
    assert staged.normalization_status == "rejected"
    assert staged.normalization_error


def test_production_code_has_no_direct_pluang_host_or_browser_impersonation() -> None:
    app_root = Path(__file__).parents[1] / "app"
    production = "\n".join(
        path.read_text(encoding="utf-8") for path in app_root.rglob("*.py")
    ).lower()

    assert "indo-stock-api-v2.pluang.com" not in production
    for forbidden in ("sec-ch-ua", "user-agent", "referer", "x-request-id"):
        assert forbidden not in production
