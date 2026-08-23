import argparse
import asyncio
from datetime import date

from app.core.config import get_settings
from app.db.session import Database
from app.providers.pluang import PluangProvider
from app.providers.transport import QuotaAwareTransport, RequestBudget
from app.repositories.postgres import PostgresMarketRepository
from app.repositories.warehouse import PostgresWarehouseRepository
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
    budget = RequestBudget(
        daily_soft_limit=args.daily_budget or settings.provider_daily_soft_budget,
        monthly_reserve=settings.provider_monthly_reserve,
        run_limit=args.request_cap or settings.provider_canary_request_cap,
        requests_today=await warehouse.requests_today("pluang"),
    )
    transport = QuotaAwareTransport(
        provider="pluang",
        concurrency=args.concurrency,
        timeout_seconds=settings.provider_timeout_seconds,
        budget=budget,
        event_sink=warehouse.record_request,
        expect_quota_headers=False,
    )
    provider = PluangProvider(
        settings.pluang_base_url, transport, raw_payload_sink=warehouse.stage_raw_payload
    )
    service = PluangIngestionService(provider, warehouse)
    try:
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

        tickers = args.tickers or ["AADI", "BBCA", "TLKM"]
        session_date = date.fromisoformat(args.trade_date) if args.trade_date else None
        session_date = session_date or await market.latest_trade_date()
        if session_date is None:
            raise RuntimeError("no confirmed market session is stored")
        canary_results = await service.collect_canary(
            tickers, trade_date=session_date, max_pages=args.max_pages
        )
        for item in canary_results:
            detail = f" error={item.error}" if item.error else ""
            print(
                f"{item.ticker}: status={item.status} broker_rows={item.broker_rows} "
                f"trade_rows={item.trade_rows} trade_pages={item.trade_pages} "
                f"orderbook_levels={item.orderbook_levels}{detail}"
            )
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pluang warehouse mapping and canaries")
    parser.add_argument("operation", choices=["map", "canary"])
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
    args = parser.parse_args()
    if args.operation == "map" and not args.tickers and not args.all_active:
        parser.error("map requires tickers or --all-active")
    if args.operation == "canary" and len(args.tickers) > 3:
        parser.error("canary accepts at most three tickers")
    if args.operation == "canary" and args.max_pages > 3:
        parser.error("canary accepts at most three cursor pages")
    if args.operation == "canary" and (args.request_cap or 30) > 30:
        parser.error("canary request cap cannot exceed 30")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
