from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time
from decimal import Decimal
from re import fullmatch
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
ZAPI_PLUANG_NAMESPACE = "finance:pluang"
PluangPayloadSink = Callable[[RawPayloadRecord], Awaitable[None]]


class PluangProvider:
    """Normalize Pluang-source data delivered through the documented Zapi gateway."""

    name = "pluang"
    gateway = "zapi"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        transport: QuotaAwareTransport,
        raw_payload_sink: PluangPayloadSink | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ZAPI_API_KEY is required for finance:pluang")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._raw_payload_sink = raw_payload_sink

    async def resolve_instrument(self, ticker: str) -> InstrumentMappingRecord:
        code = _ticker(ticker)
        payload = await self._get("resolve", {"code": code})
        raw = self._raw_record("resolve", code, payload)
        try:
            body = _unwrap_zapi_pluang(payload, dataset="resolve", ticker=code)
            instrument_id = body.get("stockId")
            if not isinstance(instrument_id, int) or instrument_id <= 0:
                raise ValueError("finance:pluang stockId must be a positive integer")
            result = InstrumentMappingRecord(
                ticker=code,
                provider_instrument_id=str(instrument_id),
                provider_ticker=code,
                mapping_status="mapped",
                source="zapi-finance:pluang-resolve",
            )
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result

    async def get_broker_summary(
        self, ticker: str, trade_date: date
    ) -> tuple[list[BrokerFlowRecord], dict[str, object]]:
        code = _ticker(ticker)
        payload = await self._get(
            "broker-summary",
            {
                "code": code,
                "startDate": trade_date.isoformat(),
                "endDate": trade_date.isoformat(),
                "net": "true",
            },
        )
        raw = self._raw_record(
            "broker-summary", code, payload, date_from=trade_date, date_to=trade_date
        )
        try:
            result = map_pluang_broker_summary(payload, code)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def get_running_trades(
        self,
        ticker: str,
        trade_date: date,
        *,
        cursor: str | None = None,
    ) -> tuple[RunningTradesPage, dict[str, object]]:
        code = _ticker(ticker)
        params = {"code": code}
        if cursor:
            params["cursor"] = cursor
        payload = await self._get("running-trades", params)
        raw = self._raw_record(
            "running-trades",
            code,
            payload,
            date_from=trade_date,
            date_to=trade_date,
            cursor_value=cursor,
        )
        try:
            result = map_pluang_running_trades(payload, code, trade_date)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def get_orderbook(
        self, ticker: str
    ) -> tuple[OrderbookSnapshotRecord, dict[str, object]]:
        code = _ticker(ticker)
        payload = await self._get("orderbook", {"code": code})
        raw = self._raw_record("orderbook", code, payload)
        try:
            result = map_pluang_orderbook(payload, code)
        except ValueError as error:
            await self._stage(raw, "rejected", str(error))
            raise
        await self._stage(raw, "normalized", None)
        return result, payload

    async def _get(
        self, endpoint: str, params: dict[str, str]
    ) -> dict[str, object]:
        endpoint_name = f"{ZAPI_PLUANG_NAMESPACE}/{endpoint}"
        return await self._transport.get_json(
            dataset=endpoint_name,
            endpoint_name=endpoint_name,
            url=f"{self._base_url}/{endpoint}",
            params=params,
            headers={"x-api-key": self._api_key},
        )

    def _raw_record(
        self,
        endpoint: str,
        ticker: str,
        payload: dict[str, object],
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        cursor_value: str | None = None,
    ) -> RawPayloadRecord:
        return RawPayloadRecord(
            provider=self.name,
            gateway=self.gateway,
            source_provider=self.name,
            dataset=f"{ZAPI_PLUANG_NAMESPACE}/{endpoint}",
            instrument_key=ticker,
            date_from=date_from,
            date_to=date_to,
            cursor_value=cursor_value,
            payload=payload,
            normalization_status="staged",
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


def map_pluang_broker_summary(
    payload: dict[str, object], ticker: str
) -> list[BrokerFlowRecord]:
    code = _ticker(ticker)
    body = _unwrap_zapi_pluang(payload, dataset="broker-summary", ticker=code)
    buyers = body.get("buyers")
    sellers = body.get("sellers")
    if not isinstance(buyers, list) or not isinstance(sellers, list):
        raise ValueError("finance:pluang broker buyers and sellers must be lists")
    capped = body.get("capped")
    if not isinstance(capped, bool):
        raise ValueError("finance:pluang broker capped flag must be boolean")
    count = body.get("count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("finance:pluang broker count must be non-negative")
    date_from = date.fromisoformat(str(body.get("startDate")))
    date_to = date.fromisoformat(str(body.get("endDate")))
    source_scope = "top_n" if capped else "complete"
    source_top_n = count if capped else None
    output: list[BrokerFlowRecord] = []
    for side, rows in (("BUY", buyers), ("SELL", sellers)):
        for rank, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError("finance:pluang broker row must be an object")
            output.append(
                _broker_side(
                    row,
                    code,
                    date_from,
                    date_to,
                    rank,
                    side,
                    source_scope,
                    source_top_n,
                )
            )
    return output


def map_pluang_running_trades(
    payload: dict[str, object], ticker: str, trade_date: date
) -> RunningTradesPage:
    code = _ticker(ticker)
    body = _unwrap_zapi_pluang(payload, dataset="running-trades", ticker=code)
    rows = body.get("items")
    if not isinstance(rows, list):
        raise ValueError("finance:pluang running-trades items must be a list")
    records: list[TradePrintRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("finance:pluang running-trades item must be an object")
        sequence = str(row.get("sequence", ""))
        if not sequence or sequence in seen:
            raise ValueError("finance:pluang running-trades has duplicate or missing sequence")
        seen.add(sequence)
        action = str(row.get("action", "")).upper()
        if action not in {"BUY", "SELL"}:
            raise ValueError("finance:pluang running-trades action must be BUY or SELL")
        execution_time = time.fromisoformat(str(row["time"]))
        lots = int(row["lots"])
        records.append(
            TradePrintRecord(
                ticker=code,
                provider_sequence=sequence,
                trade_date=trade_date,
                executed_at=datetime.combine(trade_date, execution_time, tzinfo=JAKARTA),
                price=Decimal(str(row["price"])),
                lots=lots,
                shares=lots * 100,
                aggressor_action=action,
            )
        )
    next_cursor = body.get("nextCursor")
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise ValueError("finance:pluang nextCursor must be a string")
    return RunningTradesPage(records=records, next_cursor=next_cursor)


def map_pluang_orderbook(
    payload: dict[str, object], ticker: str
) -> OrderbookSnapshotRecord:
    code = _ticker(ticker)
    body = _unwrap_zapi_pluang(payload, dataset="orderbook", ticker=code)
    levels: list[OrderbookLevelRecord] = []
    for key, side in (("bids", "BID"), ("asks", "ASK")):
        rows = body.get(key)
        if not isinstance(rows, list):
            raise ValueError(f"finance:pluang orderbook {key} must be a list")
        for rank, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError("finance:pluang orderbook level must be an object")
            levels.append(
                OrderbookLevelRecord(
                    side=side,
                    level_rank=rank,
                    price=Decimal(str(row["price"])),
                    lots=int(str(row["lots"])),
                )
            )
    bids = [level.price for level in levels if level.side == "BID"]
    asks = [level.price for level in levels if level.side == "ASK"]
    best_bid = max(bids) if bids else None
    best_ask = min(asks) if asks else None
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("finance:pluang gateway timestamp is missing")
    return OrderbookSnapshotRecord(
        ticker=code,
        observed_at=datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        levels=levels,
    )


def _unwrap_zapi_pluang(
    payload: dict[str, object], *, dataset: str, ticker: str
) -> dict[str, object]:
    body = payload.get("data")
    if not isinstance(body, dict):
        raise ValueError(f"finance:pluang {dataset} data must be an object")
    if body.get("source") != "pluang":
        raise ValueError(f"finance:pluang {dataset} source must be pluang")
    if body.get("code") != ticker:
        raise ValueError(f"finance:pluang {dataset} code mismatch")
    return body


def _broker_side(
    row: dict[str, object],
    ticker: str,
    date_from: date,
    date_to: date,
    rank: int,
    side: str,
    source_scope: str,
    source_top_n: int | None,
) -> BrokerFlowRecord:
    broker = row.get("broker")
    if not isinstance(broker, str) or not broker.strip():
        raise ValueError("finance:pluang broker code is missing")
    lots = int(str(row["lots"]))
    return BrokerFlowRecord(
        ticker=ticker,
        trade_date_from=date_from,
        trade_date_to=date_to,
        broker_code=broker,
        side=side,
        rank=rank,
        lots=lots,
        shares=lots * 100,
        value_idr=Decimal(str(row["value"])),
        average_price=Decimal(str(row["averagePrice"])),
        source_scope=source_scope,
        source_top_n=source_top_n,
    )


def _ticker(value: str) -> str:
    code = value.strip().upper()
    if not fullmatch(r"[A-Z0-9]{1,12}", code):
        raise ValueError("invalid IDX ticker")
    return code
