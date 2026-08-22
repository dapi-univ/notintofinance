import argparse
import asyncio
from datetime import date

from app.core.config import get_settings
from app.db.session import Database
from app.providers.factory import create_provider
from app.repositories.postgres import PostgresMarketRepository
from app.services.ingestion import IngestionService


async def _ingest(tickers: list[str], date_from: date | None, date_to: date | None) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for persistent ingestion")
    database = Database(settings.database_url)
    try:
        service = IngestionService(create_provider(settings), PostgresMarketRepository(database))
        for ticker in tickers:
            inserted, updated = await service.ingest_ticker(
                ticker.upper(), date_from=date_from, date_to=date_to
            )
            print(f"{ticker.upper()}: inserted={inserted} updated={updated}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest EOD history into Supabase PostgreSQL")
    parser.add_argument("tickers", nargs="+", help="IDX ticker symbols")
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat)
    parser.add_argument("--to", dest="date_to", type=date.fromisoformat)
    args = parser.parse_args()
    asyncio.run(_ingest(args.tickers, args.date_from, args.date_to))


if __name__ == "__main__":
    main()
