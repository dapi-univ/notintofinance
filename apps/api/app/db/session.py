from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Database:
    def __init__(self, url: str):
        normalized = normalize_database_url(url)
        options: dict[str, object] = {"pool_pre_ping": True}
        if normalized.startswith("postgresql+asyncpg://"):
            options.update(pool_size=5, max_overflow=5, pool_recycle=1800)
        self.engine: AsyncEngine = create_async_engine(normalized, **options)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
