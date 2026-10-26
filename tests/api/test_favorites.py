import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.api.cookies import SESSION_COOKIE
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import BaseMemberCreate
from acervo.services.session_service import SessionService

MakeTree = Callable[..., Awaitable[Any]]


async def _favorite(client: httpx.AsyncClient, node_id: Any, before_id: Any = None) -> httpx.Response:
    return await client.put(f"/v1/nodes/{node_id}/favorite", json={"before_id": before_id and str(before_id)})


async def _listed(client: httpx.AsyncClient) -> list[tuple[str, str]]:
    response = await client.get("/v1/favorites")
    assert response.status_code == 200, response.text
    return [(node["kb_id"], node["path"]) for node in response.json()]


async def test_add_order_and_remove(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    bradesco = await make_tree({"Residencial": ["Emissão.md"]}, name="Bradesco")
    porto = await make_tree({"Sinistros.md": None}, name="Porto")
    emissao, sinistros, folder = bradesco["Residencial/Emissão.md"], porto["Sinistros.md"], bradesco["Residencial"]
    assert await _listed(client) == []

    first = await _favorite(client, emissao.id)
    assert (first.status_code, first.json()["favorite"]) == (200, True)
    assert (await _favorite(client, sinistros.id, before_id=emissao.id)).status_code == 200
    assert (await _favorite(client, folder.id)).status_code == 200
    assert await _listed(client) == [
        (str(porto.kb.id), "Sinistros"),
        (str(bradesco.kb.id), "Residencial/Emissão"),
        (str(bradesco.kb.id), "Residencial"),
    ]

    assert (await _favorite(client, folder.id, before_id=sinistros.id)).status_code == 200
    assert (await _favorite(client, sinistros.id)).status_code == 200
    assert [path for _, path in await _listed(client)] == ["Residencial", "Residencial/Emissão", "Sinistros"]

    removed = await client.delete(f"/v1/nodes/{emissao.id}/favorite")
    assert (removed.status_code, removed.json()["favorite"]) == (200, False)
    assert [path for _, path in await _listed(client)] == ["Residencial", "Sinistros"]
    not_a_favorite = await _favorite(client, folder.id, before_id=emissao.id)
    assert (not_a_favorite.status_code, not_a_favorite.json()["error"]) == (422, "validation")


async def test_trashed_node_or_base_is_hidden_until_restored(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    bradesco = await make_tree({"Residencial": ["Emissão.md"]}, name="Bradesco")
    porto = await make_tree({"Sinistros.md": None}, name="Porto")
    emissao, sinistros = bradesco["Residencial/Emissão.md"], porto["Sinistros.md"]
    await _favorite(client, emissao.id)
    await _favorite(client, sinistros.id)

    assert (await client.delete(f"/v1/nodes/{bradesco['Residencial'].id}")).status_code == 200
    assert [path for _, path in await _listed(client)] == ["Sinistros"]
    assert (await client.post(f"/v1/nodes/{bradesco['Residencial'].id}/restore")).status_code == 200
    assert [path for _, path in await _listed(client)] == ["Residencial/Emissão", "Sinistros"]

    assert (await client.delete(f"/v1/kbs/{porto.kb.id}")).status_code == 200
    assert [path for _, path in await _listed(client)] == ["Residencial/Emissão"]
    assert (await client.post(f"/v1/kbs/{porto.kb.id}/restore")).status_code == 200
    assert [path for _, path in await _listed(client)] == ["Residencial/Emissão", "Sinistros"]


async def test_a_file_cannot_be_a_favorite(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"CG 2026.pdf": None})

    refused = await _favorite(client, tree["CG 2026.pdf"].id)

    assert (refused.status_code, refused.json()["error"]) == (422, "validation")
    assert await _listed(client) == []


async def test_unknown_node_is_404(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Emissão.md": None})
    unknown = uuid.uuid4()

    for response in (
        await _favorite(client, unknown),
        await _favorite(client, tree["Emissão.md"].id, before_id=unknown),
        await client.delete(f"/v1/nodes/{unknown}/favorite"),
    ):
        assert (response.status_code, response.json()["error"]) == (404, "not_found")


async def test_favorites_are_per_account(
    client: httpx.AsyncClient,
    app: FastAPI,
    make_tree: MakeTree,
    make_account: Callable[..., Awaitable[AccountRead]],
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    tree = await make_tree({"Emissão.md": None, "Sinistros.md": None, "Coberturas.md": None})
    emissao, sinistros, coberturas = tree["Emissão.md"], tree["Sinistros.md"], tree["Coberturas.md"]
    bia = await make_account(email="bia@example.com", name="Bia")
    async with UnitOfWork(session_factory) as uow:
        await uow.base_members.create(BaseMemberCreate(kb_id=tree.kb.id, account_id=bia.id, role="reader"))
        token = await SessionService(uow, test_settings.session_days).create(bia.id, None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://api.test", cookies={SESSION_COOKIE: token}
    ) as other:
        await _favorite(client, emissao.id)
        await _favorite(client, sinistros.id)
        await _favorite(other, sinistros.id)
        await _favorite(other, coberturas.id, before_id=sinistros.id)
        await other.delete(f"/v1/nodes/{emissao.id}/favorite")

        assert [path for _, path in await _listed(client)] == ["Emissão", "Sinistros"]
        assert [path for _, path in await _listed(other)] == ["Coberturas", "Sinistros"]
        children = (await other.get(f"/v1/kbs/{tree.kb.id}/children")).json()
        assert {node["title"]: node["favorite"] for node in children} == {
            "Emissão": False,
            "Sinistros": True,
            "Coberturas": True,
        }
