import pytest
from httpx import ASGITransport, AsyncClient

from acervo.api.app import app
from acervo.store.db import get_session


@pytest.fixture
async def client(session):
    async def same_session():
        yield session

    app.dependency_overrides[get_session] = same_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
