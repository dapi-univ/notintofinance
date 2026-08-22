import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request

from app.schemas.api import (
    DataStatusResponse,
    HistoryResponse,
    StockDetailResponse,
    StockListItemResponse,
)
from app.services.market import MarketService

router = APIRouter()
Ticker = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,12}$")]


def _service(request: Request) -> MarketService:
    return request.app.state.market_service  # type: ignore[no-any-return]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stocks", response_model=list[StockListItemResponse])
async def stocks(request: Request) -> list[StockListItemResponse]:
    return await _service(request).list_stocks()


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
    limit: Annotated[int, Query(ge=1, le=2000)] = 520,
) -> HistoryResponse:
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", ticker):
        raise HTTPException(status_code=422, detail="Invalid ticker")
    result = await _service(request).get_history(
        ticker.upper(),
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        as_of=date.today(),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result


@router.get("/data/status", response_model=DataStatusResponse)
async def data_status(request: Request) -> DataStatusResponse:
    return await _service(request).get_status(as_of=date.today())
