from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.db.session import Database
from app.providers.factory import create_provider
from app.repositories.base import MarketRepository
from app.repositories.memory import MemoryMarketRepository
from app.repositories.postgres import PostgresMarketRepository
from app.repositories.warehouse import PostgresWarehouseRepository
from app.services.ingestion import seed_mock_repository
from app.services.market import MarketService
from app.services.warehouse_read import WarehouseReadService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database: Database | None = None
        repository: MarketRepository
        if resolved.database_url:
            database = Database(resolved.database_url)
            repository = PostgresMarketRepository(database)
            app.state.warehouse_service = WarehouseReadService(
                PostgresWarehouseRepository(
                    database, raw_retention_days=resolved.raw_payload_retention_days
                )
            )
        else:
            repository = MemoryMarketRepository()
            app.state.warehouse_service = None

        provider = create_provider(resolved)
        if repository.kind == "memory":
            await seed_mock_repository(provider, repository)
        app.state.market_service = MarketService(
            repository,
            provider=provider.name,
            is_mock=provider.name == "mock",
        )
        yield
        if database:
            await database.dispose()

    app = FastAPI(
        title="IDX Terminal API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.parsed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()
