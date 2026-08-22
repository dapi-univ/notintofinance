from app.providers.mock import MockMarketDataProvider
from app.repositories.memory import MemoryMarketRepository
from app.services.ingestion import IngestionService


async def test_duplicate_ingestion_is_an_idempotent_upsert() -> None:
    repository = MemoryMarketRepository()
    service = IngestionService(MockMarketDataProvider(), repository)

    first_inserted, first_updated = await service.ingest_ticker("BBCA", limit=30)
    second_inserted, second_updated = await service.ingest_ticker("BBCA", limit=30)

    assert (first_inserted, first_updated) == (30, 0)
    assert (second_inserted, second_updated) == (0, 30)
    assert len(await repository.get_history("BBCA", date_from=None, date_to=None, limit=100)) == 30
