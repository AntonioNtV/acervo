import io
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.session_service import SessionService

PHOTO = Path(__file__).parent.parent / "fixtures" / "files" / "photo.png"

MakeAccount = Callable[..., Awaitable[AccountRead]]
SignIn = Callable[[AccountRead], Awaitable[httpx.AsyncClient]]


@pytest.fixture
async def sign_in(app: FastAPI, test_settings: Settings) -> AsyncIterator[SignIn]:
    """A client of its own with a new session of the account, as another browser would be."""
    clients: list[httpx.AsyncClient] = []

    async def make(account: AccountRead) -> httpx.AsyncClient:
        async with UnitOfWork(app.state.session_factory) as uow:
            token = await SessionService(uow, test_settings.session_days).create(account.id, None)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://api.test", cookies={SESSION_COOKIE: token}
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()


async def test_preferences_saved_on_one_session_show_on_another(sign_in: SignIn, make_account: MakeAccount) -> None:
    ana = await make_account()
    laptop, phone = await sign_in(ana), await sign_in(ana)
    preferences = {"theme": "dark", "page_width": "wide", "language": "en", "start_page": "bases"}

    saved = await laptop.put("/v1/account/preferences", json=preferences)
    seen = await phone.get("/v1/account")

    assert saved.status_code == 200, saved.text
    assert seen.json()["preferences"] == preferences


async def test_photo_upload_fetch_and_delete(sign_in: SignIn, make_account: MakeAccount) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com", name="Bia")
    mine, other = await sign_in(ana), await sign_in(bia)

    uploaded = await mine.put("/v1/account/photo", files={"file": ("eu.png", PHOTO.read_bytes())})
    photo_url = uploaded.json()["photo_url"]
    fetched = await other.get(photo_url)
    removed = await mine.delete("/v1/account/photo")
    gone = await other.get(photo_url)

    assert uploaded.status_code == 200, uploaded.text
    assert fetched.status_code == 200
    assert fetched.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert Image.open(io.BytesIO(fetched.content)).size == (256, 256)
    assert removed.json()["photo_url"] is None
    assert gone.status_code == 404
