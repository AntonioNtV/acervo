from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from acervo.core.settings import Settings


def async_url(url: str) -> str:
    """Accepts a plain `postgresql://` URL, as tools and docs write it, and gives the asyncpg one."""
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(async_url(settings.database_url), pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
