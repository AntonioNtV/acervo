from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.api.main import create_app
from acervo.core.settings import Settings


@pytest.fixture
async def app(test_settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[FastAPI]:
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        # Requests run on the test's connection, so what they write is rolled back with it.
        app.state.session_factory = session_factory
        yield app


@pytest.fixture
async def client(app: FastAPI, test_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    headers = {"X-API-Key": test_settings.api_key.get_secret_value()}
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test", headers=headers) as client:
        yield client
