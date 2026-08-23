import argparse
import asyncio
from datetime import date
from decimal import Decimal

from app.core.config import get_settings
from app.db.session import Database
from app.providers.pluang import PluangProvider
from app.providers.transport import QuotaAwareTransport, RequestBudget
from app.repositories.postgres import PostgresMarketRepository
from app.repositories.warehouse import PostgresWarehouseRepository
from app.services.collection import (
    MarketCollectionService,
    prioritize_market_candidates,
    request_economics,
)
from app.services.warehouse import PluangIngestionService


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for warehouse ingestion")
    database = Database(settings.database_url)
    warehouse = PostgresWarehouseRepository(
        database, raw_retention_days=settings.raw_payload_retention_days
    )
    market = PostgresMarketRepository(database)
    latest_quota = await warehouse.latest_quota("zapi")
    remaining_month = latest_quota.get("remaining_month") if latest_quota else None
    run_limit = args.request_cap or settings.provider_canary_request_cap
    budget = RequestBudget(
        daily_soft_limit=args.daily_budget or settings.provider_daily_soft_budget,
        monthly_reserve=settings.provider_monthly_reserve,
        run_limit=run_limit,
        requests_today=await warehouse.requests_today("zapi"),
        remaining_month=remaining_month if isinstance(remaining_month, int) else None,
    )
    transport = QuotaAwareTransport(
        provider="zapi",
        concurrency=args.concurrency,
        timeout_seconds=settings.provider_timeout_seconds,
        budget=budget,
        event_sink=warehouse.record_request,
        expect_quota_headers=True,
    )
    provider = PluangProvider(
        settings.zapi_api_key or "",
        settings.zapi_pluang_base_url,
        transport,
        raw_payload_sink=warehouse.stage_raw_payload,
    )
    service = PluangIngestionService(provider, warehouse)
    collection = MarketCollectionService(provider, warehouse)
    try:
        if args.operation != "dry-run" and not args.dry_run:
            purged = await warehouse.purge_expired_raw_payloads()
            if purged:
                print(f"expired_raw_payloads_purged={purged}")
        if args.operation == "map":
            tickers = (
                await warehouse.mapping_candidates(include_terminal=args.include_terminal)
                if args.all_active
                else args.tickers
            )
            if args.max_symbols is not None:
                tickers = tickers[: args.max_symbols]
            if not tickers:
                raise RuntimeError("no mapping candidates selected")
            if args.dry_run:
                print(f"selected={len(tickers)} write=false tickers={','.join(tickers)}")
                return
            mapping_result = await service.bootstrap_mappings(
                tickers, concurrency=args.concurrency
            )
            print(
                f"mapped={mapping_result.mapped} unsupported={mapping_result.unsupported} "
                f"ambiguous={mapping_result.ambiguous} "
                f"transient_failed={mapping_result.transient_failed}"
            )
            return

        if args.operation == "dry-run":
            candidates = prioritize_market_candidates(
                await warehouse.collection_candidates(mapped_only=True),
                strategic_watchlist=args.strategic_tickers,
            )
            sizes = list(dict.fromkeys([len(candidates), 500, 250, 100, 50]))
            available_month = (
                max(0, int(remaining_month) - settings.provider_monthly_reserve)
                if isinstance(remaining_month, int)
                else 0
            )
            print(
                f"eligible={len(candidates)} available_month_after_reserve={available_month} "
                "selection=deterministic"
            )
            print("stock-summary daily=1 monthly=22 expected=market-wide")
            for dataset, per_ticker in (
                ("broker-summary", 1),
                ("tradebook", 1),
                ("running-trades-lower-bound", 5),
            ):
                economics = request_economics(
                    per_ticker_requests=per_ticker, universe_sizes=sizes
                )
                print(
                    dataset
                    + " "
                    + " ".join(
                        f"u{size}=daily:{daily},monthly:{monthly}"
                        for size, (daily, monthly) in economics.items()
                    )
                )
            print(
                "priority_head=" + ",".join(item.ticker for item in candidates[:20])
            )
            return

        tickers = args.tickers or ["AADI", "BBCA", "TLKM"]
        session_date = date.fromisoformat(args.trade_date) if args.trade_date else None
        session_date = session_date or await market.latest_trade_date()
        if session_date is None:
            raise RuntimeError("no confirmed market session is stored")
        if args.operation in {"broker", "tradebook", "running"}:
            candidates = prioritize_market_candidates(
                await warehouse.collection_candidates(mapped_only=True),
                strategic_watchlist=args.strategic_tickers,
            )
            if args.all_active:
                tickers = [item.ticker for item in candidates]
                safe_limit = run_limit // (args.max_pages if args.operation == "running" else 1)
                tickers = tickers[:safe_limit]
            if args.max_symbols is not None:
                tickers = tickers[: args.max_symbols]
            if args.dry_run:
                print(
                    f"dataset={args.operation} eligible={len(candidates)} "
                    f"selected={len(tickers)} write=false tickers={','.join(tickers)}"
                )
                return
            if args.operation == "broker":
                results = await collection.collect_broker_daily(
                    tickers, trade_date=session_date, concurrency=args.concurrency
                )
            elif args.operation == "tradebook":
                results = await collection.collect_tradebook(
                    tickers, trade_date=session_date, concurrency=args.concurrency
                )
            else:
                prices = {
                    item.ticker: item.latest_close
                    for item in candidates
                    if item.latest_close is not None
                }
                results = await collection.collect_running_trades(
                    tickers,
                    trade_date=session_date,
                    reference_prices=prices,
                    min_trade_value_idr=Decimal(str(args.min_trade_value_idr)),
                    action=args.action,
                    max_pages=args.max_pages,
                    concurrency=args.concurrency,
                )
            for collection_item in results:
                detail = (
                    f" error={collection_item.error}" if collection_item.error else ""
                )
                print(
                    f"{collection_item.ticker}: dataset={collection_item.dataset} "
                    f"status={collection_item.status} requests={collection_item.requests} "
                    f"fetched={collection_item.rows_fetched} "
                    f"retained={collection_item.rows_retained} "
                    f"cursor={collection_item.cursor_remaining}{detail}"
                )
            return

        canary_results = await service.collect_canary(
            tickers,
            trade_date=session_date,
            max_pages=args.max_pages,
            compare_existing=args.compare_existing,
        )
        for canary_item in canary_results:
            detail = f" error={canary_item.error}" if canary_item.error else ""
            print(
                f"{canary_item.ticker}: status={canary_item.status} "
                f"broker_rows={canary_item.broker_rows} "
                f"trade_rows={canary_item.trade_rows} "
                f"trade_pages={canary_item.trade_pages} "
                f"orderbook_levels={canary_item.orderbook_levels}{detail}"
            )
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded Pluang warehouse collectors")
    parser.add_argument(
        "operation", choices=["map", "canary", "broker", "tradebook", "running", "dry-run"]
    )
    parser.add_argument("tickers", nargs="*")
    parser.add_argument("--all-active", action="store_true")
    parser.add_argument("--include-terminal", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--trade-date")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--daily-budget", type=int)
    parser.add_argument("--request-cap", type=int)
    parser.add_argument("--compare-existing", action="store_true")
    parser.add_argument("--min-trade-value-idr", type=Decimal, default=Decimal("0"))
    parser.add_argument("--action", choices=["BUY", "SELL"])
    parser.add_argument("--strategic-tickers", nargs="*", default=[])
    args = parser.parse_args()
    if args.operation == "map" and not args.tickers and not args.all_active:
        parser.error("map requires tickers or --all-active")
    if args.operation == "canary" and len(args.tickers) > 3:
        parser.error("canary accepts at most three tickers")
    if args.operation == "canary" and args.max_pages > 3:
        parser.error("canary accepts at most three cursor pages")
    if args.operation == "canary" and (args.request_cap or 30) > 30:
        parser.error("canary request cap cannot exceed 30")
    if args.operation in {"broker", "tradebook", "running"} and not (
        args.tickers or args.all_active
    ):
        parser.error(f"{args.operation} requires tickers or --all-active")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
