from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, AccountUpdate
from acervo.schemas.notification import Notification
from acervo.schemas.organization import OrganizationRecord
from acervo.services.mailer import FakeMailer, MailTemplate, Unsubscribe
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Any]]


async def _notify_invites(app: FastAPI, account_id: UUID, on: bool) -> None:
    async with UnitOfWork(app.state.session_factory) as uow:
        await uow.accounts.update(account_id, AccountUpdate(notify_invites=on))
        await uow.commit()


def _sent(app: FastAPI, template: MailTemplate) -> list[Unsubscribe | None]:
    mailer: FakeMailer = app.state.mailer
    return [mail.unsubscribe for mail in mailer.sent if mail.template == template]


async def test_notifications_and_time_zone_are_saved_with_the_preferences(client: httpx.AsyncClient) -> None:
    preferences = {
        "theme": "system",
        "page_width": "default",
        "language": "pt-BR",
        "start_page": "last",
        "notify_invites": False,
        "notify_followed": True,
        "timezone": "Europe/Lisbon",
    }
    before = (await client.get("/v1/account")).json()["preferences"]

    saved = await client.put("/v1/account/preferences", json=preferences)
    unknown = await client.put("/v1/account/preferences", json={**preferences, "timezone": "Mars/Olympus"})

    assert (before["notify_invites"], before["notify_followed"], before["timezone"]) == (
        True,
        False,
        "America/Sao_Paulo",
    )
    assert saved.json()["preferences"] == preferences
    assert (unknown.status_code, unknown.json()["error"]) == (422, "validation")
    assert (await client.get("/v1/account")).json()["preferences"] == preferences


async def test_sign_up_keeps_a_known_time_zone_and_falls_back_to_sao_paulo(anon_client: httpx.AsyncClient) -> None:
    async def sign_up(email: str, timezone: str | None) -> str:
        body = {"name": "Ana", "email": email, "password": "senha-de-teste", "timezone": timezone}
        response = await anon_client.post("/v1/auth/sign-up", json=body)
        assert response.status_code == 201, response.text
        return str(response.json()["preferences"]["timezone"])

    assert await sign_up("lisboa@example.com", "Europe/Lisbon") == "Europe/Lisbon"
    assert await sign_up("marte@example.com", "Mars/Olympus") == "America/Sao_Paulo"
    assert await sign_up("nenhum@example.com", None) == "America/Sao_Paulo"


async def test_base_shared_goes_only_with_invites_on(
    app: FastAPI,
    client: httpx.AsyncClient,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: MakeTree,
) -> None:
    ana_id = UUID((await client.get("/v1/account")).json()["id"])
    julia = await make_account(email="julia@example.com", name="Julia")
    team = await make_organization(ana_id, members={julia.id: "member"})
    kb_id = (await make_tree({}, organization=team.id)).kb.id
    invite = {"emails": [julia.email], "role": "reader"}

    await _notify_invites(app, julia.id, False)
    assert (await client.post(f"/v1/kbs/{kb_id}/invites", json=invite)).status_code == 201
    assert _sent(app, MailTemplate.BASE_SHARED) == []

    await _notify_invites(app, julia.id, True)
    await client.post(f"/v1/kbs/{kb_id}/invites", json=invite)
    assert _sent(app, MailTemplate.BASE_SHARED) == [Unsubscribe(julia.id, Notification.INVITES)]


async def test_role_changed_goes_only_with_invites_on(
    app: FastAPI, client: httpx.AsyncClient, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana_id = UUID((await client.get("/v1/account")).json()["id"])
    bia = await make_account(email="bia@example.com", name="Bia")
    team = await make_organization(ana_id, members={bia.id: "member"})

    await _notify_invites(app, bia.id, False)
    await client.patch(f"/v1/organizations/{team.id}/members/{bia.id}", json={"role": "admin"})
    assert _sent(app, MailTemplate.ROLE_CHANGED) == []

    await _notify_invites(app, bia.id, True)
    await client.patch(f"/v1/organizations/{team.id}/members/{bia.id}", json={"role": "member"})
    assert _sent(app, MailTemplate.ROLE_CHANGED) == [Unsubscribe(bia.id, Notification.INVITES)]


async def test_invite_accepted_goes_only_with_invites_on(
    app: FastAPI,
    client: httpx.AsyncClient,
    test_settings: Settings,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
) -> None:
    ana_id = UUID((await client.get("/v1/account")).json()["id"])
    team = await make_organization(ana_id)
    mailer: FakeMailer = app.state.mailer

    async def joins(email: str) -> None:
        person = await make_account(email=email, name="Pessoa")
        await client.post(f"/v1/organizations/{team.id}/invites", json={"emails": [email], "role": "member"})
        token = next(m.values["link"] for m in reversed(mailer.sent) if m.template == MailTemplate.ORG_INVITE)
        async with UnitOfWork(app.state.session_factory) as uow:
            session = await SessionService(uow, test_settings.session_days).create(person.id, None)
        transport = httpx.ASGITransport(app=app)
        cookies = {SESSION_COOKIE: session}
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test", cookies=cookies) as person_client:
            assert (await person_client.post("/v1/invites/accept", json={"token": token})).status_code == 200

    await _notify_invites(app, ana_id, False)
    await joins("julia@example.com")
    assert _sent(app, MailTemplate.INVITE_ACCEPTED) == []

    await _notify_invites(app, ana_id, True)
    await joins("caio@example.com")
    assert _sent(app, MailTemplate.INVITE_ACCEPTED) == [Unsubscribe(ana_id, Notification.INVITES)]
