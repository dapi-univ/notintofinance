from datetime import date

from app.repositories.warehouse import PostgresWarehouseRepository
from app.schemas.api import (
    BrokerFlowItemResponse,
    BrokerFlowResponse,
    CoverageResponse,
    OrderbookLevelResponse,
    OrderbookSnapshotResponse,
    ProviderQuotaResponse,
    QuotaStatusResponse,
    TradePrintResponse,
    TradesResponse,
)


class WarehouseReadService:
    def __init__(self, repository: PostgresWarehouseRepository) -> None:
        self._repository = repository

    async def broker_flow(self, ticker: str, date_from: date, date_to: date) -> BrokerFlowResponse:
        rows = await self._repository.broker_flow(ticker, date_from, date_to)
        scope = rows[0].source_scope if rows else "top_n"
        top_n = rows[0].source_top_n if rows else 10
        return BrokerFlowResponse(
            ticker=ticker,
            source_scope=scope,
            source_top_n=top_n,
            rows=[
                BrokerFlowItemResponse(
                    trade_date_from=row.trade_date_from,
                    trade_date_to=row.trade_date_to,
                    broker_code=row.broker_code,
                    broker_name=row.broker_name,
                    side=row.side,
                    rank=row.rank,
                    lots=row.lots,
                    shares=row.shares,
                    value_idr=row.value_idr,
                    average_price=row.average_price,
                    provider=row.provider,
                    source_scope=row.source_scope,
                    source_top_n=row.source_top_n,
                )
                for row in rows
            ],
        )

    async def trades(
        self,
        ticker: str,
        date_from: date,
        date_to: date,
        *,
        limit: int,
        cursor: int | None,
    ) -> TradesResponse:
        rows = await self._repository.trades(
            ticker, date_from, date_to, limit=limit + 1, cursor=cursor
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        return TradesResponse(
            ticker=ticker,
            rows=[
                TradePrintResponse(
                    id=row.id,
                    provider_sequence=row.provider_sequence,
                    trade_date=row.trade_date,
                    executed_at=row.executed_at,
                    price=row.price,
                    lots=row.lots,
                    shares=row.shares,
                    aggressor_action=row.aggressor_action,
                    provider=row.provider,
                )
                for row in page
            ],
            next_cursor=page[-1].id if has_more and page else None,
        )

    async def latest_orderbook(self, ticker: str) -> OrderbookSnapshotResponse | None:
        result = await self._repository.latest_orderbook(ticker)
        if not result:
            return None
        snapshot, levels = result
        return OrderbookSnapshotResponse(
            ticker=ticker,
            provider=snapshot.provider,
            observed_at=snapshot.observed_at,
            best_bid=snapshot.best_bid,
            best_ask=snapshot.best_ask,
            spread=snapshot.spread,
            levels=[
                OrderbookLevelResponse(
                    side=level.side,
                    level_rank=level.level_rank,
                    price=level.price,
                    lots=level.lots,
                )
                for level in levels
            ],
        )

    async def coverage(self) -> CoverageResponse:
        return CoverageResponse.model_validate(await self._repository.coverage())

    async def quota_status(self) -> QuotaStatusResponse:
        providers: list[ProviderQuotaResponse] = []
        for provider in ("zapi", "pluang"):
            latest = await self._repository.latest_quota(provider)
            providers.append(
                ProviderQuotaResponse(
                    provider=provider,
                    observed_at=latest.get("observed_at") if latest else None,  # type: ignore[arg-type]
                    requests_today=await self._repository.requests_today(provider),
                    limit=latest.get("limit") if latest else None,  # type: ignore[arg-type]
                    remaining_minute=latest.get("remaining_minute") if latest else None,  # type: ignore[arg-type]
                    remaining_month=latest.get("remaining_month") if latest else None,  # type: ignore[arg-type]
                    plan_expired=latest.get("plan_expired") if latest else None,  # type: ignore[arg-type]
                    warning=latest.get("warning") if latest else None,  # type: ignore[arg-type]
                )
            )
        return QuotaStatusResponse(providers=providers)
