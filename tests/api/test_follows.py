from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.db.models import Account, PageVersion
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.session_service import SessionService

MakeTree = Callable[..., Awaitable[Any]]


async def _following(client: httpx.AsyncClient, node_id: Any) -> bool:
    response = await client.get(f"/v1/pages/{node_id}")
    assert response.status_code == 200, response.text
    following: bool = response.json()["following"]
    return following


async def test_follow_and_unfollow_are_idempotent(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    page = (await make_tree({"Emissão.md": None}))["Emissão.md"]
    assert await _following(client, page.id) is False

    for _ in range(2):
        assert (await client.put(f"/v1/pages/{page.id}/follow")).status_code == 204
        assert await _following(client, page.id) is True
    for _ in range(2):
        assert (await client.delete(f"/v1/pages/{page.id}/follow")).status_code == 204
        assert await _following(client, page.id) is False


async def test_only_pages_can_be_followed(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["CG 2026.pdf"]})

    for node in (tree["Residencial"], tree["Residencial/CG 2026.pdf"]):
        refused = await client.put(f"/v1/pages/{node.id}/follow")
        assert (refused.status_code, refused.json()["error"]) == (422, "validation")


async def test_a_page_out_of_reach_is_404(
    app: FastAPI,
    make_tree: MakeTree,
    make_account: Callable[..., Awaitable[AccountRead]],
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    page = (await make_tree({"Emissão.md": None}))["Emissão.md"]
    bia = await make_account(email="bia@example.com", name="Bia")
    async with UnitOfWork(session_factory) as uow:
        token = await SessionService(uow, test_settings.session_days).create(bia.id, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://api.test", cookies={SESSION_COOKIE: token}
    ) as bia_client:
        for response in (
            await bia_client.put(f"/v1/pages/{page.id}/follow"),
            await bia_client.delete(f"/v1/pages/{page.id}/follow"),
        ):
            assert (response.status_code, response.json()["error"]) == (404, "not_found")


async def test_a_saved_version_has_its_author(
    client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession, default_account_id: Any
) -> None:
    page = (await make_tree({"Emissão.md": None}))["Emissão.md"]

    saved = await client.put(f"/v1/pages/{page.id}/text", json={"markdown": "Cinco dias.\n", "revision": 0})
    assert saved.status_code == 200, saved.text
    assert (await client.post(f"/v1/pages/{page.id}/leave")).status_code == 204

    author = await session.scalar(
        select(PageVersion.author_id).where(PageVersion.markdown == "Cinco dias.\n", PageVersion.node_id == page.id)
    )
    assert author == default_account_id


async def test_a_duplicated_page_has_its_author(
    client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession, default_account_id: Any
) -> None:
    page = (await make_tree({"Emissão.md": None}))["Emissão.md"]

    copy = await client.post(f"/v1/nodes/{page.id}/duplicate")
    assert copy.status_code == 201, copy.text

    author = await session.scalar(select(PageVersion.author_id).where(PageVersion.node_id == copy.json()["id"]))
    assert author == default_account_id


async def test_history_lists_each_versions_author(
    client: httpx.AsyncClient,
    make_tree: MakeTree,
    session: AsyncSession,
    make_account: Callable[..., Awaitable[AccountRead]],
) -> None:
    page = (await make_tree({"Emissão.md": None}))["Emissão.md"]
    bia = await make_account(email="bia@example.com", name="Bia")
    by_bia = PageVersion(node_id=page.id, markdown="Da Bia.\n", author_id=bia.id)
    old = PageVersion(node_id=page.id, markdown="Antiga.\n", author_known=False)
    session.add_all([by_bia, old])
    await session.flush()

    async def authors() -> list[tuple[Any, Any, Any]]:
        history = (await client.get(f"/v1/pages/{page.id}/versions")).json()
        by_id = {v["id"]: (v["author_id"], v["author"], v["author_known"]) for v in history}
        return [by_id[str(by_bia.id)], by_id[str(old.id)]]

    assert await authors() == [(str(bia.id), "Bia", True), (None, None, False)]
    await session.execute(delete(Account).where(Account.id == bia.id))
    assert await authors() == [(None, None, True), (None, None, False)]
