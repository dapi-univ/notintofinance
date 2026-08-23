import argparse
import asyncio

from app.core.config import get_settings
from app.db.session import Database
from app.providers.factory import create_provider
from app.providers.transport import QuotaAwareTransport, RequestBudget
from app.repositories.postgres import PostgresMarketRepository
from app.repositories.warehouse import PostgresWarehouseRepository
from app.schemas.warehouse import RawPayloadRecord
from app.services.ingestion import EodBatchIngestionService, IngestionMode


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for persistent ingestion")
    database = Database(settings.database_url)
    repository = PostgresMarketRepository(database)
    warehouse = PostgresWarehouseRepository(
        database, raw_retention_days=settings.raw_payload_retention_days
    )
    budget = RequestBudget(
        daily_soft_limit=args.daily_budget or settings.provider_daily_soft_budget,
        monthly_reserve=settings.provider_monthly_reserve,
        run_limit=args.request_cap,
        requests_today=await warehouse.requests_today("zapi"),
    )
    transport = QuotaAwareTransport(
        provider="zapi",
        concurrency=args.concurrency,
        timeout_seconds=settings.provider_timeout_seconds,
        budget=budget,
        event_sink=warehouse.record_request,
        expect_quota_headers=True,
    )
    async def stage_payload(
        dataset: str,
        instrument_key: str | None,
        payload: dict[str, object],
        status: str,
        error: str | None,
    ) -> None:
        await warehouse.stage_raw_payload(
            RawPayloadRecord(
                provider="zapi",
                dataset=dataset,
                instrument_key=instrument_key,
                payload=payload,
                normalization_status=status,
                normalization_error=error,
            )
        )

    provider = create_provider(
        settings, transport=transport, raw_payload_sink=stage_payload
    )

    async def record_failure(ticker: str, reason: str, retryable: bool, terminal: bool) -> None:
        await warehouse.record_quality_event(
            provider="zapi",
            dataset="stock-history",
            ticker=ticker,
            reason_code=reason,
            retryable=retryable,
            terminal=terminal,
        )

    service = EodBatchIngestionService(provider, repository, failure_recorder=record_failure)
    try:
        async with warehouse.advisory_lock("zapi:stock-history"):
            if args.discover_only:
                universe = await provider.get_stock_universe()
                print(f"discovered={universe.total} write=false")
                return
            if not args.skip_universe_sync:
                sync = await service.synchronize_universe()
                print(
                    "universe "
                    f"discovered={sync.discovered} inserted={sync.inserted} "
                    f"updated={sync.updated} deactivated={sync.deactivated}"
                )
            if args.sync_universe_only:
                return

            if args.resume:
                tickers = await service.resumable_tickers(include_terminal=args.include_terminal)
            elif args.resume_failed:
                tickers = await service.failed_tickers()
            elif args.all_active:
                tickers = [item.stock.ticker for item in await repository.list_stocks()]
            else:
                tickers = args.tickers
            if args.max_symbols is not None:
                tickers = tickers[: args.max_symbols]
            if not tickers:
                raise RuntimeError("no ticker symbols selected")
            if args.dry_run:
                print(f"selected={len(tickers)} write=false tickers={','.join(tickers)}")
                return

            result = await service.ingest(
                tickers,
                mode=IngestionMode(args.mode),
                target_sessions=args.sessions,
                revision_days=args.revision_days,
                concurrency=args.concurrency,
            )
        for item in result.results:
            detail = f" error={item.error}" if item.error else ""
            print(
                f"{item.ticker}: status={item.status} mode={item.mode.value} "
                f"received={item.rows_received} inserted={item.rows_inserted} "
                f"updated={item.rows_updated} rejected={item.rows_rejected}{detail}"
            )
        print(f"completed={result.completed} failed={result.failed}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize IDX securities and ingest resumable EOD history"
    )
    parser.add_argument("tickers", nargs="*", help="selected IDX ticker symbols")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all-active", action="store_true")
    selection.add_argument(
        "--resume",
        action="store_true",
        help="ingest failed, interrupted, and not-yet-attempted active symbols",
    )
    selection.add_argument("--resume-failed", action="store_true")
    selection.add_argument("--discover-only", action="store_true")
    selection.add_argument("--sync-universe-only", action="store_true")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in IngestionMode],
        default=IngestionMode.AUTO.value,
    )
    parser.add_argument("--sessions", type=int, default=260)
    parser.add_argument("--revision-days", type=int, default=14)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--daily-budget", type=int)
    parser.add_argument("--request-cap", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-terminal",
        action="store_true",
        help="explicitly retry terminally classified EOD failures",
    )
    parser.add_argument(
        "--skip-universe-sync",
        action="store_true",
        help="reuse the synchronized universe for a safe resume",
    )
    args = parser.parse_args()
    if (
        not args.tickers
        and not args.all_active
        and not args.resume
        and not args.resume_failed
        and not args.discover_only
        and not args.sync_universe_only
    ):
        parser.error("select tickers or an operational mode")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
