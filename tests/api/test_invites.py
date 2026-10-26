from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
from fastapi import FastAPI

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord
from acervo.services.access_service import AccessService
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]


async def test_an_invited_person_joins_through_the_emailed_link(
    app: FastAPI,
    client: httpx.AsyncClient,
    anon_client: httpx.AsyncClient,
    test_settings: Settings,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
) -> None:
    ana_id = UUID((await client.get("/v1/auth/me")).json()["id"])
    team = await make_organization(ana_id)
    julia = await make_account(email="julia@example.com", name="Julia Lima")
    mailer: FakeMailer = app.state.mailer

    invited = await client.post(
        f"/v1/organizations/{team.id}/invites", json={"emails": ["julia@example.com"], "role": "member"}
    )
    assert invited.status_code == 201, invited.text
    [mail] = [sent for sent in mailer.sent if sent.template == MailTemplate.ORG_INVITE]
    token = mail.values["link"]

    preview = (await anon_client.get(f"/v1/invites/by-token/{token}")).json()
    assert (preview["organization"], preview["email"], preview["role"], preview["expired"]) == (
        "Seguros SA",
        "julia@example.com",
        "member",
        False,
    )

    async with UnitOfWork(app.state.session_factory) as uow:
        julia_token = await SessionService(uow, test_settings.session_days).create(julia.id, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://api.test", cookies={SESSION_COOKIE: julia_token}
    ) as julia_client:
        accepted = await julia_client.post("/v1/invites/accept", json={"token": token})
        # The link opened again once joined, as after Criar conta, still says where it leads; to no one else.
        again = await julia_client.post("/v1/invites/accept", json={"token": token})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["organization_id"] == str(team.id)
    assert again.json()["organization_id"] == str(team.id)
    assert (await client.post("/v1/invites/accept", json={"token": token})).json()["error"] == "code_invalid"

    async with UnitOfWork(app.state.session_factory) as uow:
        assert await AccessService(uow).org_role(julia.id, team.id) == "member"
    assert (await client.get(f"/v1/organizations/{team.id}/invites")).json() == []
    assert mailer.sent[-1].template == MailTemplate.INVITE_ACCEPTED


async def test_an_invite_takes_at_most_50_emails(
    client: httpx.AsyncClient, make_organization: MakeOrganization
) -> None:
    team = await make_organization(UUID((await client.get("/v1/auth/me")).json()["id"]))
    emails = [f"pessoa{n}@example.com" for n in range(51)]

    response = await client.post(f"/v1/organizations/{team.id}/invites", json={"emails": emails, "role": "member"})

    assert (response.status_code, response.json()["error"]) == (422, "validation")
