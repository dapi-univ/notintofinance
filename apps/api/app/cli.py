import argparse
import asyncio

from app.core.config import get_settings
from app.db.session import Database
from app.providers.factory import create_provider
from app.repositories.postgres import PostgresMarketRepository
from app.services.ingestion import EodBatchIngestionService, IngestionMode


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for persistent ingestion")
    provider = create_provider(settings)

    if args.discover_only:
        universe = await provider.get_stock_universe()
        print(f"discovered={universe.total} write=false")
        return

    database = Database(settings.database_url)
    repository = PostgresMarketRepository(database)
    service = EodBatchIngestionService(provider, repository)
    try:
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
            tickers = await service.resumable_tickers()
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
