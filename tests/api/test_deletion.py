import io
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.db.models import File, Node, PageVersion
from acervo.db.models.account import Account
from acervo.db.models.kb import Kb
from acervo.db.models.organization import Organization
from acervo.db.models.page_attachment import PageAttachment
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord, OrgRole
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.session_service import SessionService
from acervo.services.storage import Storage
from tests.conftest import Tree

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Tree]]
SignIn = Callable[[AccountRead], Awaitable[httpx.AsyncClient]]


@pytest.fixture
async def sign_in(app: FastAPI, test_settings: Settings) -> AsyncIterator[SignIn]:
    """A client of its own with a new session of the account."""
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


async def _put(storage: Storage, key: str) -> str:
    await storage.put(key, io.BytesIO(b"bytes"), 5)
    return key


async def _stored(storage: Storage, key: str) -> bool:
    try:
        async for _ in storage.stream(key):
            break
    except ClientError:
        return False
    return True


async def _count(session: AsyncSession, model: type, **filters: object) -> int:
    query = select(func.count()).select_from(model)
    for name, value in filters.items():
        query = query.where(getattr(model, name) == value)
    return await session.scalar(query) or 0


async def _org_with_stored_base(
    session: AsyncSession, storage: Storage, make_tree: MakeTree, organization_id: UUID, shared_sha: str
) -> list[str]:
    """A base whose file, cover, attachment and logo are in the bucket; the keys, the shared attachment's last."""
    tree = await make_tree({"Docs": ["Manual.md", "CG 2026.pdf"]}, organization=organization_id)
    page, pdf = tree["Docs/Manual.md"], tree["Docs/CG 2026.pdf"]
    page.cover = "image:cover1"
    session.add(PageAttachment(page_id=page.id, name="a.txt", sha256="attach1", mime="text/plain", size=5))
    session.add(PageAttachment(page_id=page.id, name="b.txt", sha256=shared_sha, mime="text/plain", size=5))
    organization = await session.get_one(Organization, organization_id)
    organization.logo_key = f"organization/{organization_id}/logo.png"
    await session.flush()
    file_key = await session.scalar(select(File.storage_key).where(File.node_id == pdf.id))
    assert file_key is not None
    return [
        await _put(storage, key)
        for key in (
            file_key,
            "covers/cover1",
            "attachments/attach1",
            organization.logo_key,
            f"attachments/{shared_sha}",
        )
    ]


@pytest.mark.parametrize(("role", "status"), [("owner", 204), ("admin", 403), ("member", 403)])
async def test_only_an_owner_deletes_an_organization_and_the_other_members_are_told(
    app: FastAPI,
    session: AsyncSession,
    sign_in: SignIn,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: MakeTree,
    role: OrgRole,
    status: int,
) -> None:
    storage: Storage = app.state.storage
    ana, bia = await make_account(), await make_account(email="bia@example.com", name="Bia")
    actor = {"owner": ana, "admin": bia, "member": bia}[role]
    organization = await make_organization(ana.id, members={bia.id: role if role != "owner" else "member"})
    keys = await _org_with_stored_base(session, storage, make_tree, organization.id, "shared1")
    # Another organization's page holds the same attachment bytes.
    other = await make_organization(bia.id, name="Outra")
    page = (await make_tree(["Outra.md"], organization=other.id))["Outra.md"]
    session.add(PageAttachment(page_id=page.id, name="b.txt", sha256="shared1", mime="text/plain", size=5))
    await session.flush()

    deleted = await (await sign_in(actor)).delete(f"/v1/organizations/{organization.id}")

    assert deleted.status_code == status, deleted.text
    mailer: FakeMailer = app.state.mailer
    if status == 403:
        assert await _count(session, Organization, id=organization.id) == 1
        assert mailer.sent == []
        return
    assert await _count(session, Organization, id=organization.id) == 0
    assert await _count(session, Kb, organization_id=organization.id) == 0
    assert [await _stored(storage, key) for key in keys] == [False, False, False, False, True]
    assert [(m.to, m.template, m.values["bases"]) for m in mailer.sent] == [
        ("bia@example.com", MailTemplate.ORG_DELETED, "1")
    ]


async def test_a_pessoal_is_not_deleted_as_an_organization(
    session: AsyncSession, sign_in: SignIn, make_account: MakeAccount
) -> None:
    ana = await make_account()
    personal = await session.scalar(select(Organization.id).where(Organization.personal_of == ana.id))

    refused = await (await sign_in(ana)).delete(f"/v1/organizations/{personal}")

    assert (refused.status_code, refused.json()["error"]) == (403, "personal_org")


async def test_deleting_an_account_takes_its_pessoal_and_sole_owned_teams_and_keeps_shared_ones(
    app: FastAPI,
    session: AsyncSession,
    sign_in: SignIn,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
    make_tree: MakeTree,
) -> None:
    storage: Storage = app.state.storage
    ana = await make_account()
    bia = await make_account(email="bia@example.com", name="Bia")
    caio = await make_account(email="caio@example.com", name="Caio")
    sole = await make_organization(ana.id, name="Só da Ana", members={bia.id: "member", caio.id: "admin"})
    shared = await make_organization(ana.id, name="Dividida", members={bia.id: "owner"})
    personal = await session.scalar(select(Organization.id).where(Organization.personal_of == ana.id))
    assert personal is not None
    keys = await _org_with_stored_base(session, storage, make_tree, sole.id, "shared2")
    await make_tree(["Nota.md"], name="Minha", organization=personal)
    page = (await make_tree(["Escrita.md"], organization=shared.id))["Escrita.md"]
    session.add(PageVersion(node_id=page.id, markdown="# Escrita\n\ntexto da Ana\n", author_id=ana.id))
    account = await session.get_one(Account, ana.id)
    account.photo_key = await _put(storage, f"account/{ana.id}/photo.png")
    await session.flush()
    client = await sign_in(ana)

    deleted = await client.delete("/v1/account")

    assert deleted.status_code == 204, deleted.text
    assert (await client.get("/v1/account")).status_code == 401
    assert await _count(session, Account, id=ana.id) == 0
    assert [await _count(session, Organization, id=o) for o in (sole.id, personal, shared.id)] == [0, 0, 1]
    assert await _count(session, Node, id=page.id) == 1
    authors = await session.scalars(select(PageVersion.author_id).where(PageVersion.node_id == page.id))
    assert set(authors) == {None}
    assert [await _stored(storage, key) for key in [*keys, account.photo_key]] == [False] * 6
    mailer: FakeMailer = app.state.mailer
    assert sorted((m.to, m.template, m.values["bases"]) for m in mailer.sent) == [
        ("ana@example.com", MailTemplate.ACCOUNT_DELETED, "1"),
        ("bia@example.com", MailTemplate.ORG_DELETED, "1"),
        ("caio@example.com", MailTemplate.ORG_DELETED, "1"),
    ]
    assert mailer.sent[-1].template is MailTemplate.ACCOUNT_DELETED


async def test_deleting_needs_a_recent_sign_in(
    session: AsyncSession, sign_in: SignIn, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana = await make_account()
    organization = await make_organization(ana.id)
    client = await sign_in(ana)
    await session.execute(text("update session set created_at = created_at - interval '11 minutes'"))

    responses = [await client.delete(f"/v1/organizations/{organization.id}"), await client.delete("/v1/account")]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(403, "reauthentication_required")] * 2
    assert await _count(session, Account, id=ana.id) == 1
