import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request

from app.schemas.api import (
    BrokerFlowResponse,
    CoverageResponse,
    DataStatusResponse,
    HistoryResponse,
    OrderbookSnapshotResponse,
    QuotaStatusResponse,
    StockDetailResponse,
    StockListItemResponse,
    TradesResponse,
)
from app.services.market import HistoryTimeframe, MarketService
from app.services.trade_cursor import InvalidTradeCursor
from app.services.warehouse_read import WarehouseReadService

router = APIRouter()
Ticker = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,12}$")]


def _service(request: Request) -> MarketService:
    return request.app.state.market_service  # type: ignore[no-any-return]


def _warehouse(request: Request) -> WarehouseReadService:
    service = getattr(request.app.state, "warehouse_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Warehouse database is not configured")
    return service  # type: ignore[no-any-return]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stocks", response_model=list[StockListItemResponse])
async def stocks(
    request: Request,
    query: Annotated[str | None, Query(alias="q", max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> list[StockListItemResponse]:
    return (await _service(request).list_stocks(query))[:limit]


@router.get("/stocks/{ticker}", response_model=StockDetailResponse)
async def stock(request: Request, ticker: Ticker) -> StockDetailResponse:
    result = await _service(request).get_stock(ticker.upper())
    if not result:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result


@router.get("/stocks/{ticker}/history", response_model=HistoryResponse)
async def history(
    request: Request,
    ticker: Ticker,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int | None, Query(ge=1, le=2000)] = None,
    timeframe: HistoryTimeframe = HistoryTimeframe.SIX_MONTHS,
) -> HistoryResponse:
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker")
    result = await _service(request).get_history(
        ticker.upper(),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        timeframe=timeframe,
        as_of=date.today(),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result


@router.get("/data/status", response_model=DataStatusResponse)
async def data_status(request: Request) -> DataStatusResponse:
    return await _service(request).get_status(as_of=date.today())


@router.get("/stocks/{ticker}/broker-flow", response_model=BrokerFlowResponse)
async def broker_flow(
    request: Request,
    ticker: Ticker,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> BrokerFlowResponse:
    if date_to < date_from or (date_to - date_from).days > 31:
        raise HTTPException(status_code=422, detail="Broker-flow range must be 0 to 31 days")
    return await _warehouse(request).broker_flow(ticker.upper(), date_from, date_to)


@router.get("/stocks/{ticker}/trades", response_model=TradesResponse)
async def trades(
    request: Request,
    ticker: Ticker,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> TradesResponse:
    if date_to < date_from or (date_to - date_from).days > 7:
        raise HTTPException(status_code=422, detail="Trade range must be 0 to 7 days")
    try:
        return await _warehouse(request).trades(
            ticker.upper(), date_from, date_to, limit=limit, cursor=cursor
        )
    except InvalidTradeCursor as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/stocks/{ticker}/orderbook/latest", response_model=OrderbookSnapshotResponse)
async def latest_orderbook(
    request: Request, ticker: Ticker
) -> OrderbookSnapshotResponse:
    result = await _warehouse(request).latest_orderbook(ticker.upper())
    if result is None:
        raise HTTPException(status_code=404, detail="Orderbook snapshot not found")
    return result


@router.get("/data/coverage", response_model=CoverageResponse)
async def coverage(request: Request) -> CoverageResponse:
    return await _warehouse(request).coverage()


@router.get("/data/quota-status", response_model=QuotaStatusResponse)
async def quota_status(request: Request) -> QuotaStatusResponse:
    return await _warehouse(request).quota_status()
