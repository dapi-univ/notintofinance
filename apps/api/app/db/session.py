import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class UnsafeDatabaseTarget(RuntimeError):
    pass


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def is_managed_supabase_url(url: str) -> bool:
    host = (make_url(normalize_database_url(url)).host or "").lower()
    return host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")


def is_pytest_process() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


class Database:
    def __init__(self, url: str):
        normalized = normalize_database_url(url)
        self.is_managed_supabase = is_managed_supabase_url(normalized)
        if self.is_managed_supabase and is_pytest_process():
            raise UnsafeDatabaseTarget(
                "tests cannot connect to a managed Supabase database; use an isolated "
                "local test database or mocks"
            )
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
