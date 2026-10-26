from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.account import AccountRepository
from acervo.repositories.base_member import BaseMemberRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import BaseMemberCreate, BaseRole
from acervo.services.session_service import SessionService

MakeTree = Callable[..., Awaitable[Any]]
Make = Callable[..., Awaitable[Any]]
PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"
PDF = (PDFS / "simple.pdf").read_bytes()
# The routers whose every route checks the person's role in the base.
CONTENT = {"nodes", "pages", "files", "covers", "exports", "attachments", "favorites"}


@pytest.fixture
async def bia(make_account: Make) -> AccountRead:
    """Someone outside Seguros SA: whatever she reaches there is through the base role she is given."""
    account: AccountRead = await make_account(email="bia@example.com", name="Bia")
    return account


@pytest.fixture
async def bia_client(
    app: FastAPI, bia: AccountRead, session_factory: async_sessionmaker[AsyncSession], test_settings: Settings
) -> AsyncIterator[httpx.AsyncClient]:
    async with UnitOfWork(session_factory) as uow:
        token = await SessionService(uow, test_settings.session_days).create(bia.id, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test", cookies={SESSION_COOKIE: token}) as c:
        yield c


@pytest.fixture
async def base(client: httpx.AsyncClient, session: AsyncSession, make_organization: Make, make_tree: MakeTree) -> Any:
    """A base of Seguros SA, owned by the client's account, with a page and an uploaded file."""
    ana = await AccountRepository(session).by_email("ana@example.com")
    assert ana is not None
    organization = await make_organization(ana.id)
    tree = await make_tree({"Emissão de apólice.md": None}, organization=organization.id)
    uploaded = await client.post(f"/v1/kbs/{tree.kb.id}/files", files={"file": ("CG 2026.pdf", PDF, "application/pdf")})
    assert uploaded.status_code == 201
    tree.file_id = uploaded.json()["id"]
    return tree


async def _give(session: AsyncSession, kb_id: UUID, account_id: UUID, role: BaseRole) -> None:
    await BaseMemberRepository(session).create(BaseMemberCreate(kb_id=kb_id, account_id=account_id, role=role))


async def _put_text(client: httpx.AsyncClient, page_id: UUID) -> httpx.Response:
    revision = (await client.get(f"/v1/pages/{page_id}")).json()["revision"]
    return await client.put(f"/v1/pages/{page_id}/text", json={"markdown": "# Novo\n", "revision": revision})


async def _upload(client: httpx.AsyncClient, kb_id: UUID) -> httpx.Response:
    return await client.post(
        f"/v1/kbs/{kb_id}/files",
        files={"file": ("Outra.pdf", (PDFS / "protected.pdf").read_bytes(), "application/pdf")},
    )


async def test_a_reader_reads_and_downloads_but_cannot_change(
    bia_client: httpx.AsyncClient, bia: AccountRead, base: Any, session: AsyncSession
) -> None:
    await _give(session, base.kb.id, bia.id, "reader")
    page_id = base["Emissão de apólice.md"].id

    page = await bia_client.get(f"/v1/pages/{page_id}")
    raw = await bia_client.get(f"/v1/files/{base.file_id}/raw")
    saved = await _put_text(bia_client, page_id)
    uploaded = await _upload(bia_client, base.kb.id)

    assert (page.status_code, raw.status_code, raw.content) == (200, 200, PDF)
    assert (saved.status_code, saved.json()["error"]) == (403, "forbidden")
    assert (uploaded.status_code, uploaded.json()["error"]) == (403, "forbidden")


async def test_an_editor_changes_pages_and_uploads(
    bia_client: httpx.AsyncClient, bia: AccountRead, base: Any, session: AsyncSession
) -> None:
    await _give(session, base.kb.id, bia.id, "editor")

    saved = await _put_text(bia_client, base["Emissão de apólice.md"].id)
    uploaded = await _upload(bia_client, base.kb.id)

    assert (saved.status_code, uploaded.status_code) == (200, 201)


async def test_someone_without_a_role_reaches_no_route(app: FastAPI, bia_client: httpx.AsyncClient, base: Any) -> None:
    ids = {"kb_id": str(base.kb.id), "node_id": str(base["Emissão de apólice.md"].id)}
    routes = [
        (method, path)
        for path, operations in app.openapi()["paths"].items()
        for method, operation in operations.items()
        if CONTENT & set(operation["tags"]) and "{" in path
    ]
    assert len(routes) > 30

    statuses = {
        (method, path): (await bia_client.request(method, path.format_map(_Ids(ids)))).status_code
        for method, path in routes
    }

    assert {route: status for route, status in statuses.items() if status not in (403, 404)} == {}


async def test_a_node_does_not_move_to_another_organization(
    client: httpx.AsyncClient, base: Any, make_tree: MakeTree
) -> None:
    personal = await make_tree({"Rascunho.md": None}, name="Minha base")

    moved = await client.post(
        f"/v1/nodes/{personal['Rascunho.md'].id}/move", json={"kb_id": str(base.kb.id), "parent_id": None}
    )

    assert (moved.status_code, moved.json()["error"]) == (403, "forbidden")


class _Ids(dict[str, str]):
    """The base's and the page's ids where a path asks for them, any id elsewhere."""

    def __missing__(self, key: str) -> str:
        return "00000000-0000-0000-0000-000000000000"
