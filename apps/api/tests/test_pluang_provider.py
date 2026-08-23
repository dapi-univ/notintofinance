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


def _fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_broker_summary_preserves_top_n_scope_and_lot_share_units() -> None:
    rows = map_pluang_broker_summary(_fixture("pluang_broker_summary.json"), "BBCA")
    assert [(row.side, row.broker_code) for row in rows] == [("BUY", "AK"), ("SELL", "RX")]
    assert rows[0].source_scope == "top_n"
    assert rows[0].source_top_n == 10
    assert rows[0].shares == rows[0].lots * 100


def test_running_trades_maps_jakarta_session_and_cursor() -> None:
    page = map_pluang_running_trades(
        _fixture("pluang_running_trades.json"), "BBCA", date(2026, 8, 21)
    )
    assert page.next_cursor == "MjI2OTQ="
    assert page.records[0].shares == 2900
    assert page.records[0].executed_at.utcoffset().total_seconds() == 7 * 3600
    assert page.records[0].aggressor_action == "SELL"


def test_running_trades_rejects_duplicate_provider_sequences() -> None:
    payload = _fixture("pluang_running_trades.json")
    body = payload["data"]
    assert isinstance(body, dict)
    rows = body["rt"]
    assert isinstance(rows, list)
    rows[1] = rows[0]
    with pytest.raises(ValueError, match="duplicate"):
        map_pluang_running_trades(payload, "BBCA", date(2026, 8, 21))


def test_orderbook_is_resting_liquidity_with_derived_spread() -> None:
    snapshot = map_pluang_orderbook(_fixture("pluang_orderbook.json"), "BBCA")
    assert snapshot.best_bid == 6425
    assert snapshot.best_ask == 6450
    assert snapshot.spread == 25
    assert [(level.side, level.lots) for level in snapshot.levels] == [
        ("BID", 10955),
        ("ASK", 75223),
    ]


@pytest.mark.parametrize("fixture", ["pluang_mapping.json", "pluang_orderbook.json"])
def test_pluang_fixtures_use_valid_wrapped_envelope(fixture: str) -> None:
    payload = _fixture(fixture)
    assert payload["statusCode"] == 200
    assert isinstance(payload["data"], dict)


async def test_pluang_provider_stages_rejected_payload_after_validation_failure() -> None:
    payload = _fixture("pluang_orderbook.json")
    body = payload["data"]
    assert isinstance(body, dict)
    body["bids"] = [{"p": 0, "l": 1}]
    transport = AsyncMock()
    transport.get_json.return_value = payload
    sink = AsyncMock()
    provider = PluangProvider(
        "https://provider.invalid", transport, raw_payload_sink=sink
    )

    with pytest.raises(ValueError):
        await provider.get_orderbook("BBCA", "10020")

    staged = sink.await_args.args[0]
    assert staged.dataset == "orderbook"
    assert staged.normalization_status == "rejected"
    assert staged.normalization_error


async def test_pluang_provider_stages_normalized_payload() -> None:
    transport = AsyncMock()
    transport.get_json.return_value = _fixture("pluang_mapping.json")
    sink = AsyncMock()
    provider = PluangProvider(
        "https://provider.invalid", transport, raw_payload_sink=sink
    )

    mapping = await provider.resolve_instrument("BBCA")

    assert mapping.provider_instrument_id == "10020"
    staged = sink.await_args.args[0]
    assert staged.normalization_status == "normalized"
