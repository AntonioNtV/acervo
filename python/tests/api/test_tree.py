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


async def _kb(client) -> str:
    return (await client.post("/kbs", json={"name": "Seguros · Operação"})).json()["id"]


async def _node(client, kb_id: str, title: str, kind: str = "folder", parent_id: str | None = None) -> str:
    response = await client.post(f"/kbs/{kb_id}/nodes", json={"kind": kind, "title": title, "parent_id": parent_id})
    assert response.status_code == 201
    return response.json()["id"]


async def _titles(client, kb_id: str, parent_id: str | None = None) -> list[str]:
    params = {"parent_id": parent_id} if parent_id else {}
    return [node["title"] for node in (await client.get(f"/kbs/{kb_id}/children", params=params)).json()]


async def test_children_move_and_order(client) -> None:
    kb_id = await _kb(client)
    bradesco = await _node(client, kb_id, "Bradesco")
    porto = await _node(client, kb_id, "Porto")
    emission = await _node(client, kb_id, "Emissão de apólice", "page", bradesco)
    renewal = await _node(client, kb_id, "Renovação", "page", bradesco)
    assert await _titles(client, kb_id) == ["Bradesco", "Porto"]
    assert await _titles(client, kb_id, bradesco) == ["Emissão de apólice", "Renovação"]

    await client.post(f"/nodes/{renewal}/move", json={"parent_id": bradesco, "before_id": emission})
    assert await _titles(client, kb_id, bradesco) == ["Renovação", "Emissão de apólice"]

    moved = await client.post(f"/nodes/{emission}/move", json={"parent_id": porto})
    assert moved.json()["parent_id"] == porto
    assert await _titles(client, kb_id, porto) == ["Emissão de apólice"]
    assert await _titles(client, kb_id, bradesco) == ["Renovação"]

    into_itself = await client.post(f"/nodes/{bradesco}/move", json={"parent_id": bradesco})
    assert (into_itself.status_code, into_itself.json()["error"]) == (400, "ValidationError")


async def test_search(client) -> None:
    kb_id = await _kb(client)
    residencial = await _node(client, kb_id, "Residencial", parent_id=await _node(client, kb_id, "Bradesco"))
    page = await _node(client, kb_id, "Emissão de apólice", "page", residencial)

    hits = (await client.get(f"/kbs/{kb_id}/search", params={"q": "APOLICE"})).json()

    assert [(hit["id"], hit["path"]) for hit in hits] == [(page, "Bradesco/Residencial/Emissão de apólice")]


async def test_trash_and_restore_node(client) -> None:
    kb_id = await _kb(client)
    bradesco = await _node(client, kb_id, "Bradesco")
    residencial = await _node(client, kb_id, "Residencial", parent_id=bradesco)
    await _node(client, kb_id, "Emissão de apólice", "page", residencial)

    await client.delete(f"/nodes/{residencial}")
    await client.delete(f"/nodes/{bradesco}")
    assert await _titles(client, kb_id) == []
    trashed = (await client.get(f"/kbs/{kb_id}/trash")).json()
    assert {(item["title"], item["path"]) for item in trashed} == {
        ("Bradesco", "Bradesco"),
        ("Residencial", "Bradesco/Residencial"),
    }

    restored = (await client.post(f"/nodes/{residencial}/restore")).json()
    assert (restored["parent_id"], restored["to_root"]) == (None, True)
    assert await _titles(client, kb_id) == ["Residencial"]
    assert await _titles(client, kb_id, residencial) == ["Emissão de apólice"]
    assert (await client.get(f"/nodes/{bradesco}")).status_code == 404


async def test_title_clash_is_409(client) -> None:
    kb_id = await _kb(client)
    await _node(client, kb_id, "Bradesco")
    porto = await _node(client, kb_id, "Porto")

    for response in [
        await client.post(f"/kbs/{kb_id}/nodes", json={"kind": "folder", "title": "bradesco"}),
        await client.patch(f"/nodes/{porto}", json={"title": "Bradesco"}),
    ]:
        assert response.status_code == 409
        assert (response.json()["error"], response.json()["message"]) == ("ConflictError", "já existe")
    assert await _titles(client, kb_id) == ["Bradesco", "Porto"]
