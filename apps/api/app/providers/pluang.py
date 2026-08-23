import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.providers.transport import QuotaAwareTransport
from app.schemas.warehouse import (
    BrokerFlowRecord,
    InstrumentMappingRecord,
    OrderbookLevelRecord,
    OrderbookSnapshotRecord,
    RawPayloadRecord,
    RunningTradesPage,
    TradePrintRecord,
)

JAKARTA = ZoneInfo("Asia/Jakarta")
PluangPayloadSink = Callable[[RawPayloadRecord], Awaitable[None]]


class PluangProvider:
    name = "pluang"

    def __init__(
        self,
        base_url: str,
        transport: QuotaAwareTransport,
        raw_payload_sink: PluangPayloadSink | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._raw_payload_sink = raw_payload_sink

    async def resolve_instrument(self, ticker: str) -> InstrumentMappingRecord:
        code = ticker.strip().upper()
        payload = await self._get(
            "instrument-mapping",
            "description-by-code",
            {"stockCode": code},
        )
        raw = RawPayloadRecord(
            provider=self.name,
            dataset="instrument-mapping",
            instrument_key=code,
            payload=payload,
            normalization_status="staged",
        )
        try:
            body = _unwrap(payload, dataset="instrument-mapping")
            instrument_id = body.get("id")
            if instrument_id is None:
                result = InstrumentMappingRecord(
                    ticker=code,
                    provider_instrument_id=None,
                    provider_ticker=code,
                    mapping_status="unsupported",
                )
            else:
                if not isinstance(instrument_id, int) or instrument_id <= 0:
                    raise ValueError("Pluang instrument id must be a positive integer")
                result = InstrumentMappingRecord(
                    ticker=code,
                    provider_instrument_id=str(instrument_id),
                    provider_ticker=code,
                    mapping_status="mapped",
                )
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result

    async def get_broker_summary(
        self, ticker: str, instrument_id: str, trade_date: date
    ) -> tuple[list[BrokerFlowRecord], dict[str, object]]:
        payload = await self._get(
            "broker-summary",
            "broker/summary",
            {
                "stockId": instrument_id,
                "startDate": trade_date.isoformat(),
                "endDate": trade_date.isoformat(),
                "net": "true",
            },
        )
        raw = RawPayloadRecord(
            provider=self.name,
            dataset="broker-summary",
            instrument_key=instrument_id,
            date_from=trade_date,
            date_to=trade_date,
            payload=payload,
            normalization_status="staged",
        )
        try:
            result = map_pluang_broker_summary(payload, ticker)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def get_running_trades(
        self,
        ticker: str,
        instrument_id: str,
        trade_date: date,
        *,
        cursor: str | None = None,
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        params = {"stockId": instrument_id}
        if cursor:
            params["next"] = cursor
        payload = await self._get("running-trades", "market-feed/running-trades", params)
        raw = RawPayloadRecord(
            provider=self.name,
            dataset="running-trades",
            instrument_key=instrument_id,
            date_from=trade_date,
            date_to=trade_date,
            cursor_value=cursor,
            payload=payload,
            normalization_status="staged",
        )
        try:
            result = map_pluang_running_trades(payload, ticker, trade_date)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def get_orderbook(
        self, ticker: str, instrument_id: str
    ) -> tuple[OrderbookSnapshotRecord, dict[str, object]]:
        payload = await self._get("orderbook", "market-feed/orderbook", {"stockId": instrument_id})
        raw = RawPayloadRecord(
            provider=self.name,
            dataset="orderbook",
            instrument_key=instrument_id,
            payload=payload,
            normalization_status="staged",
        )
        try:
            result = map_pluang_orderbook(payload, ticker)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def _get(self, dataset: str, endpoint: str, params: dict[str, str]) -> dict[str, object]:
        return await self._transport.get_json(
            dataset=dataset,
            endpoint_name=endpoint,
            url=f"{self._base_url}/{endpoint}",
            params=params,
            headers=_browser_headers(),
        )

    async def _stage(
        self, record: RawPayloadRecord, status: str, error: str | None
    ) -> None:
        if self._raw_payload_sink:
            await self._raw_payload_sink(
                record.model_copy(
                    update={
                        "normalization_status": status,
                        "normalization_error": error,
                    }
                )
            )


def map_pluang_broker_summary(payload: dict[str, object], ticker: str) -> list[BrokerFlowRecord]:
    body = _unwrap(payload, dataset="broker-summary")
    rows = body.get("brokerSummary")
    if not isinstance(rows, list):
        raise ValueError("Pluang broker summary rows must be a list")
    date_from = date.fromisoformat(str(body.get("startDate")))
    date_to = date.fromisoformat(str(body.get("endDate")))
    output: list[BrokerFlowRecord] = []
    for rank, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError("Pluang broker summary row must be an object")
        output.extend(
            (
                _broker_side(row, ticker, date_from, date_to, rank, "BUY"),
                _broker_side(row, ticker, date_from, date_to, rank, "SELL"),
            )
        )
    return output


def map_pluang_running_trades(
    payload: dict[str, object], ticker: str, trade_date: date
) -> RunningTradesPage:
    body = _unwrap(payload, dataset="running-trades")
    rows = body.get("rt")
    if not isinstance(rows, list):
        raise ValueError("Pluang running trades rows must be a list")
    records: list[TradePrintRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Pluang running trade row must be an object")
        sequence = str(row.get("seq", ""))
        if not sequence or sequence in seen:
            raise ValueError("Pluang running trades contains duplicate or missing sequence")
        seen.add(sequence)
        action = str(row.get("action", "")).upper()
        if action not in {"BUY", "SELL"}:
            action = "UNKNOWN"
        execution_time = time.fromisoformat(str(row["time"]))
        lots = int(row["lot"])
        records.append(
            TradePrintRecord(
                ticker=ticker,
                provider_sequence=sequence,
                trade_date=trade_date,
                executed_at=datetime.combine(trade_date, execution_time, tzinfo=JAKARTA),
                price=Decimal(str(row["price"])),
                lots=lots,
                shares=lots * 100,
                aggressor_action=action,
            )
        )
    next_cursor = body.get("next")
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise ValueError("Pluang running trades next cursor must be a string")
    return RunningTradesPage(records=records, next_cursor=next_cursor)


def map_pluang_orderbook(payload: dict[str, object], ticker: str) -> OrderbookSnapshotRecord:
    body = _unwrap(payload, dataset="orderbook")
    levels: list[OrderbookLevelRecord] = []
    for key, side in (("bids", "BID"), ("asks", "ASK")):
        rows = body.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"Pluang orderbook {key} must be a list")
        for rank, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError("Pluang orderbook level must be an object")
            levels.append(
                OrderbookLevelRecord(
                    side=side,
                    level_rank=rank,
                    price=Decimal(str(row["p"])),
                    lots=int(str(row["l"])),
                )
            )
    bids = [level.price for level in levels if level.side == "BID"]
    asks = [level.price for level in levels if level.side == "ASK"]
    best_bid = max(bids) if bids else None
    best_ask = min(asks) if asks else None
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("Pluang orderbook timestamp is missing")
    return OrderbookSnapshotRecord(
        ticker=ticker,
        observed_at=datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        levels=levels,
    )


def _unwrap(payload: dict[str, object], *, dataset: str) -> dict[str, object]:
    if payload.get("statusCode") != 200:
        raise ValueError(f"Pluang {dataset} response statusCode must be 200")
    body = payload.get("data")
    if not isinstance(body, dict):
        raise ValueError(f"Pluang {dataset} data must be an object")
    return body


def _broker_side(
    row: dict[str, object],
    ticker: str,
    date_from: date,
    date_to: date,
    rank: int,
    side: str,
) -> BrokerFlowRecord:
    prefix = "buy" if side == "BUY" else "sell"
    code_field = "buyerCode" if side == "BUY" else "sellerCode"
    broker = row.get(code_field)
    if not isinstance(broker, dict) or not broker.get("value"):
        raise ValueError("Pluang broker summary code is missing")
    lots = int(str(row[f"{prefix}Lot"]))
    return BrokerFlowRecord(
        ticker=ticker,
        trade_date_from=date_from,
        trade_date_to=date_to,
        broker_code=str(broker["value"]),
        side=side,
        rank=rank,
        lots=lots,
        shares=lots * 100,
        value_idr=Decimal(str(row[f"{prefix}Value"])),
        average_price=Decimal(str(row[f"{prefix}Average"])),
    )


def _browser_headers() -> dict[str, str]:
    return {
        "accept": "application/json, text/plain, */*",
        "referer": "https://pluang.com/",
        "x-language-code": "en",
        "x-request-id": str(uuid.uuid4()),
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua": '"Not=A?Brand";v="99", "Chromium";v="151"',
        "sec-ch-ua-mobile": "?0",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0 Safari/537.36"
        ),
    }
