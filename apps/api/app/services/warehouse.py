import asyncio
from dataclasses import dataclass
from datetime import date

import httpx

from app.models.warehouse import BrokerFlowDaily
from app.providers.pluang import PluangProvider
from app.repositories.warehouse import PostgresWarehouseRepository
from app.schemas.warehouse import (
    BrokerFlowRecord,
    InstrumentMappingRecord,
    OrderbookSnapshotRecord,
    TradePrintRecord,
)


@dataclass(frozen=True)
class MappingBatchResult:
    mapped: int = 0
    unsupported: int = 0
    ambiguous: int = 0
    transient_failed: int = 0


@dataclass(frozen=True)
class MicrostructureSymbolResult:
    ticker: str
    broker_rows: int
    trade_rows: int
    orderbook_levels: int
    trade_pages: int
    status: str
    error: str | None = None


class PluangIngestionService:
    def __init__(self, provider: PluangProvider, repository: PostgresWarehouseRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def bootstrap_mappings(
        self, tickers: list[str], *, concurrency: int = 2
    ) -> MappingBatchResult:
        if not 1 <= concurrency <= 10:
            raise ValueError("concurrency must be between 1 and 10")
        semaphore = asyncio.Semaphore(concurrency)

        async def resolve(ticker: str) -> str:
            async with semaphore:
                try:
                    mapping = await self._provider.resolve_instrument(ticker)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 404:
                        mapping = InstrumentMappingRecord(
                            ticker=ticker,
                            provider_instrument_id=None,
                            provider_ticker=ticker,
                            mapping_status="unsupported",
                        )
                    else:
                        await self._record_mapping_failure(
                            ticker,
                            error,
                            retryable=(
                                error.response.status_code == 429
                                or error.response.status_code >= 500
                            ),
                        )
                        return "transient_failure"
                except (httpx.RequestError, RuntimeError) as error:
                    await self._record_mapping_failure(ticker, error, retryable=True)
                    return "transient_failure"
                except ValueError as error:
                    await self._record_mapping_failure(ticker, error, retryable=False)
                    return "ambiguous"
                await self._repository.upsert_mapping(mapping)
                return mapping.mapping_status

        statuses = await asyncio.gather(*(resolve(ticker) for ticker in dict.fromkeys(tickers)))
        return MappingBatchResult(
            mapped=statuses.count("mapped"),
            unsupported=statuses.count("unsupported"),
            ambiguous=statuses.count("ambiguous"),
            transient_failed=statuses.count("transient_failure"),
        )

    async def collect_canary(
        self,
        tickers: list[str],
        *,
        trade_date: date,
        max_pages: int = 3,
        compare_existing: bool = False,
    ) -> list[MicrostructureSymbolResult]:
        unique = list(dict.fromkeys(ticker.upper() for ticker in tickers))
        if len(unique) > 3:
            raise ValueError("microstructure canary supports at most three symbols")
        if not 1 <= max_pages <= 3:
            raise ValueError("running-trades page limit must be between one and three")
        output: list[MicrostructureSymbolResult] = []
        async with self._repository.advisory_lock(
            f"pluang:microstructure:{trade_date.isoformat()}"
        ):
            for ticker in unique:
                output.append(
                    await self._collect_symbol(
                        ticker, trade_date, max_pages, compare_existing=compare_existing
                    )
                )
        return output

    async def _collect_symbol(
        self,
        ticker: str,
        trade_date: date,
        max_pages: int,
        *,
        compare_existing: bool,
    ) -> MicrostructureSymbolResult:
        checkpoint = await self._repository.ingestion_cursor(
            ticker=ticker,
            provider="pluang",
            dataset="running-trades",
            session_date=trade_date,
        )
        instrument_key = checkpoint.instrument_key if checkpoint else ticker
        cursor = None if compare_existing else checkpoint.cursor_value if checkpoint else None
        high_water = checkpoint.high_water_mark if checkpoint else None
        mismatches: list[str] = []
        try:
            broker_blocked = (
                not compare_existing
                and await self._repository.has_terminal_quality_block(
                    ticker=ticker,
                    provider="pluang",
                    dataset="finance:pluang/broker-summary",
                )
            )
            if broker_blocked:
                broker_rows: list[BrokerFlowRecord] = []
                mismatches.append("broker-summary-blocked")
            else:
                broker_rows, _ = await self._provider.get_broker_summary(ticker, trade_date)
                broker_mismatch = compare_existing and await self._broker_mismatch(
                    ticker, trade_date, broker_rows
                )
                if broker_mismatch:
                    mismatches.append("broker-summary")
                    await self._record_comparison_mismatch(
                        ticker, "broker-summary", len(broker_rows)
                    )
                else:
                    await self._repository.upsert_broker_flow(broker_rows)

            trade_rows: list[TradePrintRecord] = []
            pages = 0
            trades_blocked = (
                not compare_existing
                and await self._repository.has_terminal_quality_block(
                    ticker=ticker,
                    provider="pluang",
                    dataset="finance:pluang/running-trades",
                )
            )
            if trades_blocked:
                mismatches.append("running-trades-blocked")
            else:
                for _ in range(max_pages):
                    page, _ = await self._provider.get_running_trades(
                        ticker, trade_date, cursor=cursor
                    )
                    pages += 1
                    trade_rows.extend(page.records)
                    cursor = page.next_cursor
                    high_water = (
                        page.records[-1].provider_sequence if page.records else high_water
                    )
                    cursor_status = (
                        "exhausted"
                        if not page.records
                        else "running"
                        if cursor
                        else "succeeded"
                    )
                    if not compare_existing:
                        await self._repository.update_cursor(
                            ticker=ticker,
                            provider="pluang",
                            dataset="running-trades",
                            instrument_key=instrument_key,
                            session_date=trade_date,
                            cursor_value=cursor,
                            high_water_mark=high_water,
                            status=cursor_status,
                        )
                    if not cursor or not page.records:
                        break
                if not compare_existing and cursor and trade_rows:
                    await self._repository.update_cursor(
                        ticker=ticker,
                        provider="pluang",
                        dataset="running-trades",
                        instrument_key=instrument_key,
                        session_date=trade_date,
                        cursor_value=cursor,
                        high_water_mark=high_water,
                        status="partial",
                    )
            deduplicated = {
                (record.trade_date, record.provider_sequence): record for record in trade_rows
            }
            if len(deduplicated) != len(trade_rows):
                raise ValueError("duplicate trade sequence across Pluang pages")
            normalized_trades = list(deduplicated.values())
            trade_comparison = (
                await self._trade_mismatch(ticker, trade_date, normalized_trades)
                if compare_existing
                else None
            )
            if trade_comparison:
                mismatches.append("running-trades")
                await self._record_comparison_mismatch(
                    ticker,
                    "running-trades",
                    len(normalized_trades),
                    comparison=trade_comparison,
                )
            elif not trades_blocked:
                await self._repository.upsert_trade_prints(normalized_trades)

            orderbook_levels = 0
            orderbook_blocked = (
                not compare_existing
                and await self._repository.has_terminal_quality_block(
                    ticker=ticker,
                    provider="pluang",
                    dataset="finance:pluang/orderbook",
                )
            )
            if orderbook_blocked:
                mismatches.append("orderbook-blocked")
            else:
                snapshot, _ = await self._provider.get_orderbook(ticker)
                orderbook_levels = len(snapshot.levels)
                orderbook_mismatch = compare_existing and await self._orderbook_mismatch(
                    ticker, snapshot
                )
                if orderbook_mismatch:
                    mismatches.append("orderbook")
                    await self._record_comparison_mismatch(
                        ticker, "orderbook", len(snapshot.levels)
                    )
                else:
                    await self._repository.insert_orderbook_snapshot(snapshot)
            result_status = (
                "blocked"
                if any(item.endswith("-blocked") for item in mismatches)
                else "comparison_mismatch"
                if mismatches
                else "partial"
                if cursor
                else "succeeded"
            )
            return MicrostructureSymbolResult(
                ticker,
                len(broker_rows),
                len(deduplicated),
                orderbook_levels,
                pages,
                result_status,
                ",".join(mismatches) or None,
            )
        except Exception as error:
            message = str(error)[:1000]
            retryable = isinstance(error, (httpx.RequestError, RuntimeError))
            await self._repository.record_quality_event(
                provider="pluang",
                dataset="microstructure",
                ticker=ticker,
                reason_code=_reason_code(error),
                retryable=retryable,
                terminal=not retryable,
                context={"message": message},
            )
            if not compare_existing:
                await self._repository.update_cursor(
                    ticker=ticker,
                    provider="pluang",
                    dataset="running-trades",
                    instrument_key=instrument_key,
                    session_date=trade_date,
                    cursor_value=cursor,
                    high_water_mark=high_water,
                    status="failed",
                    error_message=message,
                )
            return MicrostructureSymbolResult(ticker, 0, 0, 0, 0, "failed", message)

    async def _broker_mismatch(
        self, ticker: str, trade_date: date, incoming: list[BrokerFlowRecord]
    ) -> bool:
        existing = await self._repository.broker_flow(ticker, trade_date, trade_date)
        if not existing:
            return False
        return {_broker_signature(row) for row in existing} != {
            _broker_signature(row) for row in incoming
        }

    async def _trade_mismatch(
        self, ticker: str, trade_date: date, incoming: list[TradePrintRecord]
    ) -> dict[str, int] | None:
        existing = await self._repository.trades_by_sequences(
            ticker,
            trade_date,
            [record.provider_sequence for record in incoming],
        )
        existing_by_sequence = {row.provider_sequence: row for row in existing}
        mismatch_counts = {
            "executed_at": 0,
            "price": 0,
            "lots": 0,
            "shares": 0,
            "action": 0,
        }
        for record in incoming:
            row = existing_by_sequence.get(record.provider_sequence)
            if not row:
                continue
            mismatch_counts["executed_at"] += row.executed_at != record.executed_at
            mismatch_counts["price"] += row.price != record.price
            mismatch_counts["lots"] += row.lots != record.lots
            mismatch_counts["shares"] += row.shares != record.shares
            mismatch_counts["action"] += row.aggressor_action != record.aggressor_action
        if not any(mismatch_counts.values()):
            return None
        return {"overlap": len(existing), **mismatch_counts}

    async def _orderbook_mismatch(
        self, ticker: str, incoming: OrderbookSnapshotRecord
    ) -> bool:
        existing = await self._repository.latest_orderbook(ticker)
        if not existing:
            return False
        snapshot, levels = existing
        return (
            snapshot.best_bid,
            snapshot.best_ask,
            snapshot.spread,
            {(level.side, level.level_rank, level.price) for level in levels},
        ) != (
            incoming.best_bid,
            incoming.best_ask,
            incoming.spread,
            {(level.side, level.level_rank, level.price) for level in incoming.levels},
        )

    async def _record_comparison_mismatch(
        self,
        ticker: str,
        dataset: str,
        incoming_rows: int,
        *,
        comparison: dict[str, int] | None = None,
    ) -> None:
        await self._repository.record_quality_event(
            provider="pluang",
            dataset=f"finance:pluang/{dataset}",
            ticker=ticker,
            reason_code="gateway_source_comparison_mismatch",
            retryable=False,
            terminal=True,
            context={
                "gateway": "zapi",
                "source": "pluang",
                "incoming_rows": incoming_rows,
                "comparison": comparison or {},
            },
        )

    async def _record_mapping_failure(
        self, ticker: str, error: Exception, *, retryable: bool
    ) -> None:
        status = "transient_failure" if retryable else "ambiguous"
        await self._repository.upsert_mapping(
            InstrumentMappingRecord(
                ticker=ticker,
                provider_instrument_id=None,
                provider_ticker=ticker,
                mapping_status=status,
            )
        )
        await self._repository.record_quality_event(
            provider="pluang",
            dataset="instrument-mapping",
            ticker=ticker,
            reason_code=_reason_code(error),
            retryable=retryable,
            terminal=not retryable,
            context={"message": str(error)[:1000]},
        )


def _reason_code(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "provider_timeout"
    if isinstance(error, httpx.HTTPStatusError):
        return f"provider_http_{error.response.status_code}"
    if isinstance(error, httpx.RequestError):
        return "provider_network"
    if isinstance(error, ValueError):
        return "validation_failure"
    return "collector_failure"


def _broker_signature(row: BrokerFlowDaily | BrokerFlowRecord) -> tuple[object, ...]:
    return (
        row.trade_date_from,
        row.trade_date_to,
        row.broker_code,
        row.side,
        row.rank,
        row.lots,
        row.shares,
        row.value_idr,
        row.average_price,
        row.source_scope,
        row.source_top_n,
    )
