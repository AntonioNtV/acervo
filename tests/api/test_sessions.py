from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
SignIn = Callable[..., Awaitable[httpx.AsyncClient]]

CHROME_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/18.0 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
async def sign_in(app: FastAPI, test_settings: Settings) -> AsyncIterator[SignIn]:
    """A client of its own with a new session of the account, as another browser would be."""
    clients: list[httpx.AsyncClient] = []

    async def make(account: AccountRead, user_agent: str | None = None) -> httpx.AsyncClient:
        async with UnitOfWork(app.state.session_factory) as uow:
            token = await SessionService(uow, test_settings.session_days).create(account.id, user_agent)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://api.test", cookies={SESSION_COOKIE: token}
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()


async def test_sessions_lists_every_browser_and_ends_another(sign_in: SignIn, make_account: MakeAccount) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com")
    laptop, phone = await sign_in(ana, CHROME_MAC), await sign_in(ana, SAFARI_IPHONE)
    stranger = await sign_in(bia)

    listed = (await laptop.get("/v1/sessions")).json()
    by_system = {row["system"]: row for row in listed}
    phone_id, laptop_id = by_system["iPhone"]["id"], by_system["macOS"]["id"]
    current = await laptop.delete(f"/v1/sessions/{laptop_id}")
    not_hers = await stranger.delete(f"/v1/sessions/{phone_id}")
    ended = await laptop.delete(f"/v1/sessions/{phone_id}")

    assert sorted((row["browser"], row["system"], row["current"], row["method"]) for row in listed) == [
        ("Chrome", "macOS", True, "password"),
        ("Safari", "iPhone", False, "password"),
    ]
    assert (current.status_code, not_hers.status_code, ended.status_code) == (422, 404, 204)
    assert (await phone.get("/v1/account")).status_code == 401
    assert (await laptop.get("/v1/account")).status_code == 200


async def test_end_others_keeps_only_this_session(sign_in: SignIn, make_account: MakeAccount) -> None:
    ana = await make_account()
    here, there, elsewhere = await sign_in(ana), await sign_in(ana), await sign_in(ana)

    response = await here.post("/v1/sessions/end-others")

    assert response.status_code == 204, response.text
    assert [(await c.get("/v1/account")).status_code for c in (here, there, elsewhere)] == [200, 401, 401]
    assert len((await here.get("/v1/sessions")).json()) == 1


async def test_a_sensitive_change_asks_the_password_again_after_ten_minutes(
    sign_in: SignIn, make_account: MakeAccount, session: AsyncSession
) -> None:
    client = await sign_in(await make_account())
    await session.execute(text("update session set created_at = created_at - interval '11 minutes'"))
    new_password = {"password": "outra-senha-boa"}

    stale = await client.put("/v1/account/password", json=new_password)
    wrong = await client.post("/v1/sessions/reauthenticate", json={"password": "errada-errada"})
    right = await client.post("/v1/sessions/reauthenticate", json={"password": "senha-de-teste"})
    changed = await client.put("/v1/account/password", json=new_password)

    assert (stale.status_code, stale.json()["error"]) == (403, "reauthentication_required")
    assert (wrong.status_code, wrong.json()["error"]) == (401, "invalid_credentials")
    assert right.status_code == 204, right.text
    assert changed.status_code == 200, changed.text
