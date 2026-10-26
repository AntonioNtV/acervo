import csv
import io
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.passkey import PasskeyRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord
from acervo.schemas.security import PasskeyCreate
from acervo.services.mailer import MailTemplate
from acervo.services.session_service import SessionService
from acervo.services.whatsapp import FakeWhatsApp

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
SignIn = Callable[[AccountRead], Awaitable[httpx.AsyncClient]]

CHROME_MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
SAFARI_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile Safari/604.1"


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


def _sent(app: FastAPI, template: MailTemplate) -> list[Any]:
    return [mail for mail in app.state.mailer.sent if mail.template == template]


async def test_a_required_two_factor_stops_a_member_without_it_and_lets_a_passkey_through(
    app: FastAPI,
    sign_in: SignIn,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: Any,
    session: AsyncSession,
) -> None:
    ana = await make_account()
    bia, caio = await make_account(email="bia@example.com", name="Bia"), await make_account(email="caio@example.com")
    seguros = await make_organization(ana.id, members={bia.id: "member", caio.id: "member"})
    tree = await make_tree({"Emissão de apólice.md": None}, organization=seguros.id)
    passkey = PasskeyCreate(
        account_id=caio.id,
        credential_id=b"c",
        public_key=b"k",
        sign_count=0,
        transports=[],
        name="1Password",
        aaguid="",
    )
    await PasskeyRepository(session).create(passkey)
    owner, bia_client, caio_client = await sign_in(ana), await sign_in(bia), await sign_in(caio)
    pessoal = (await bia_client.post("/v1/kbs", json={"name": "Minhas notas"})).json()

    turned = await owner.patch(f"/v1/organizations/{seguros.id}", json={"require_two_factor": True})
    blocked = await bia_client.get(f"/v1/kbs/{tree.kb.id}")
    listed = await bia_client.get("/v1/kbs", params={"organization_id": str(seguros.id)})
    through = await caio_client.get(f"/v1/kbs/{tree.kb.id}")
    own = await bia_client.get(f"/v1/kbs/{pessoal['id']}")

    assert turned.status_code == 200, turned.text
    assert (turned.json()["require_two_factor"], turned.json()["password_only"]) == (True, 2)
    assert {mail.to for mail in _sent(app, MailTemplate.ORG_REQUIRES_2FA)} == {"ana@example.com", "bia@example.com"}
    assert [(r.status_code, r.json()["error"]) for r in (blocked, listed)] == [(403, "two_factor_required")] * 2
    assert (through.status_code, own.status_code) == (200, 200)


async def test_the_audit_downloads_as_csv_for_owners_only(
    sign_in: SignIn, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana = await make_account()
    bia = await make_account(email="bia@example.com", name="=HYPERLINK(1)")
    seguros = await make_organization(ana.id, members={bia.id: "member"})
    owner, member = await sign_in(ana), await sign_in(bia)
    await owner.patch(f"/v1/organizations/{seguros.id}/members/{bia.id}", json={"role": "admin"})
    await member.post("/v1/kbs", json={"name": "Sinistros", "organization_id": str(seguros.id)})
    await owner.patch(f"/v1/organizations/{seguros.id}/members/{bia.id}", json={"role": "member"})

    downloaded = await owner.get(f"/v1/organizations/{seguros.id}/audit.csv")
    refused = await member.get(f"/v1/organizations/{seguros.id}/audit.csv")

    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("text/csv")
    header, *rows = list(csv.reader(io.StringIO(downloaded.text)))
    assert header == ["created_at", "kind", "actor_name", "actor_email", "data"]
    assert [(row[1], row[2]) for row in rows] == [
        ("role_changed", "Ana"),
        ("base_created", "'=HYPERLINK(1)"),
        ("role_changed", "Ana"),
    ]
    assert (refused.status_code, refused.json()["error"]) == (403, "forbidden")


async def test_a_new_browser_is_emailed_once(
    app: FastAPI, anon_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    await make_account()
    credentials = {"email": "ana@example.com", "password": "senha-de-teste"}

    for user_agent in (CHROME_MAC, SAFARI_IPHONE, SAFARI_IPHONE, CHROME_MAC):
        signed = await anon_client.post("/v1/auth/sign-in", json=credentials, headers={"User-Agent": user_agent})
        assert signed.status_code == 200, signed.text

    [mail] = _sent(app, MailTemplate.NEW_SIGN_IN)
    assert (mail.values["browser"], mail.values["system"], mail.values["method"]) == ("Safari", "iPhone", "password")
    activity = (await anon_client.get("/v1/security/activity")).json()
    assert [(row["kind"], row["data"], row["browser"]) for row in activity][:2] == [
        ("signed_in", {"method": "password"}, "Chrome"),
        ("signed_in", {"method": "password"}, "Safari"),
    ]


async def test_a_newer_version_of_the_same_browser_is_not_a_new_browser(
    app: FastAPI, anon_client: httpx.AsyncClient, make_account: MakeAccount
) -> None:
    await make_account()
    credentials = {"email": "ana@example.com", "password": "senha-de-teste"}

    for user_agent in (CHROME_MAC, CHROME_MAC.replace("Chrome/130", "Chrome/131")):
        signed = await anon_client.post("/v1/auth/sign-in", json=credentials, headers={"User-Agent": user_agent})
        assert signed.status_code == 200, signed.text

    assert _sent(app, MailTemplate.NEW_SIGN_IN) == []


async def test_a_required_two_factor_hides_the_members_favorites_of_its_bases(
    sign_in: SignIn,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: Any,
    session: AsyncSession,
) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com", name="Bia")
    seguros = await make_organization(ana.id, members={bia.id: "member"})
    team = await make_tree({"Emissão.md": None}, organization=seguros.id)
    pessoal = await OrganizationRepository(session).get_by(personal_of=bia.id)
    assert pessoal is not None
    mine = await make_tree({"Notas.md": None}, organization=pessoal.id)
    owner, member = await sign_in(ana), await sign_in(bia)
    for node_id in (team["Emissão.md"].id, mine["Notas.md"].id):
        assert (await member.put(f"/v1/nodes/{node_id}/favorite", json={})).status_code == 200

    await owner.patch(f"/v1/organizations/{seguros.id}", json={"require_two_factor": True})
    listed = await member.get("/v1/favorites")

    assert listed.status_code == 200, listed.text
    assert [node["title"] for node in listed.json()] == ["Notas"]


async def test_adding_a_passkey_or_a_whatsapp_number_needs_a_recent_sign_in(
    app: FastAPI, client: httpx.AsyncClient, session: AsyncSession, test_settings: Settings
) -> None:
    app.state.settings = test_settings.model_copy(
        update={"whatsapp_token": SecretStr("token"), "whatsapp_phone_number_id": "1"}
    )
    app.state.whatsapp = FakeWhatsApp()
    await session.execute(text("update session set created_at = created_at - interval '11 minutes'"))
    whatsapp = {"method": "whatsapp", "phone": "+5511912345678"}

    refused = [await client.post("/v1/passkeys/register/options"), await client.post("/v1/two-factor", json=whatsapp)]
    options = await client.get("/v1/security/options")
    await client.post("/v1/sessions/reauthenticate", json={"password": "senha-de-teste"})
    allowed = [await client.post("/v1/passkeys/register/options"), await client.post("/v1/two-factor", json=whatsapp)]

    assert [(r.status_code, r.json()["error"]) for r in refused] == [(403, "reauthentication_required")] * 2
    assert options.json() == {"whatsapp_enabled": True}
    assert [r.status_code for r in allowed] == [200, 200]
    assert len(app.state.whatsapp.sent) == 1


async def test_without_a_whatsapp_sender_whatsapp_is_not_offered(client: httpx.AsyncClient) -> None:
    started = await client.post("/v1/two-factor", json={"method": "whatsapp", "phone": "+5511912345678"})
    options = await client.get("/v1/security/options")

    assert (started.status_code, started.json()["error"]) == (422, "validation")
    assert options.json() == {"whatsapp_enabled": False}
