from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.api.cookies import SESSION_COOKIE
from acervo.api.main import create_app
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.session_service import SessionService


@pytest.fixture
async def app(test_settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[FastAPI]:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        # Requests run on the test's connection, so what they write is rolled back with it.
        app.state.session_factory = session_factory
        yield app


@pytest.fixture
async def session_token(
    make_account: Callable[..., Awaitable[AccountRead]],
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> str:
    """The cookie of a live session of a signed-in account."""
    account = await make_account()
    async with UnitOfWork(session_factory) as uow:
        return await SessionService(uow, test_settings.session_days).create(account.id, None)


@pytest.fixture
async def anon_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test") as client:
        yield client


@pytest.fixture
async def client(app: FastAPI, session_token: str) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    cookies = {SESSION_COOKIE: session_token}
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test", cookies=cookies) as client:
        yield client
