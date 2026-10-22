from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from acervo.config import Settings


def async_url(url: str) -> str:
    """Accepts a plain `postgresql://` URL, as tools and docs write it, and gives the asyncpg one."""
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


@lru_cache
def engine() -> AsyncEngine:
    return create_async_engine(async_url(Settings().database_url))


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as session:
        yield session
