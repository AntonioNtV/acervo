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


async def _page(client, title: str = "Emissão de apólice") -> tuple[str, str]:
    kb_id = (await client.post("/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    response = await client.post(f"/kbs/{kb_id}/nodes", json={"kind": "page", "title": title})
    return kb_id, response.json()["id"]


async def _save(client, node_id: str, markdown: str, **extra) -> dict:
    base = (await client.get(f"/nodes/{node_id}")).json()["page"]["version_id"]
    return (await client.put(f"/nodes/{node_id}", json={"markdown": markdown, "base_version_id": base, **extra})).json()


async def test_create_page_has_version_1(client) -> None:
    _, node_id = await _page(client)

    node = (await client.get(f"/nodes/{node_id}")).json()

    assert (node["kind"], node["path"], node["versions"], node["file"]) == ("page", "Emissão de apólice", 1, None)
    assert (node["page"]["markdown"], node["page"]["draft"], node["page"]["sections"]) == ("", None, [])
    [version] = (await client.get(f"/nodes/{node_id}/versions")).json()
    assert (version["id"], version["author"]) == (node["page"]["version_id"], "user")


async def test_save_stale_is_409_with_diff(client) -> None:
    _, node_id = await _page(client)
    opened = (await client.get(f"/nodes/{node_id}")).json()["page"]["version_id"]
    await _save(client, node_id, "## Prazo\n\nCinco dias.\n")

    stale = await client.put(f"/nodes/{node_id}", json={"markdown": "Minha versão\n", "base_version_id": opened})

    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["markdown"] == "## Prazo\n\nCinco dias.\n"
    assert {"op": "add", "text": "## Prazo"} in detail["diff"]
    forced = await client.put(
        f"/nodes/{node_id}", json={"markdown": "Minha versão\n", "base_version_id": opened, "force": True}
    )
    assert forced.status_code == 200
    assert len((await client.get(f"/nodes/{node_id}/versions")).json()) == 3


async def test_draft_round_trip(client) -> None:
    _, node_id = await _page(client)
    base = (await client.get(f"/nodes/{node_id}")).json()["page"]["version_id"]

    put = await client.put(f"/nodes/{node_id}/draft", json={"markdown": "Rascunho\n", "base_version_id": base})
    assert put.json()["markdown"] == "Rascunho\n"
    draft = (await client.get(f"/nodes/{node_id}")).json()["page"]["draft"]
    assert (draft["markdown"], draft["base_version_id"]) == ("Rascunho\n", base)

    assert (await client.delete(f"/nodes/{node_id}/draft")).status_code == 204
    node = (await client.get(f"/nodes/{node_id}")).json()
    assert (node["page"]["draft"], node["versions"]) == (None, 1)


async def test_rename_fixes_links(client) -> None:
    kb_id, emission = await _page(client)
    renewal = (await client.post(f"/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Renovação"})).json()["id"]
    await _save(client, emission, "Antes da [[Renovação]] e da [[Vistoria]].\n")
    assert (await client.get(f"/nodes/{emission}")).json()["page"]["links"] == {
        "renovação": renewal,
        "vistoria": "missing",
    }

    renamed = await client.patch(f"/nodes/{renewal}", json={"title": "Renovação anual"})

    assert renamed.json()["title"] == "Renovação anual"
    page = (await client.get(f"/nodes/{emission}")).json()
    assert page["page"]["markdown"] == "Antes da [[Renovação anual]] e da [[Vistoria]].\n"
    assert page["page"]["links"] == {"renovação anual": renewal, "vistoria": "missing"}
    assert [v["author"] for v in (await client.get(f"/nodes/{emission}/versions")).json()] == ["user"] * 3


async def test_restore_version(client) -> None:
    _, node_id = await _page(client)
    await _save(client, node_id, "Primeira\n")
    await _save(client, node_id, "Segunda\n")
    newest, first, empty = (await client.get(f"/nodes/{node_id}/versions")).json()

    diff = (await client.get(f"/nodes/{node_id}/versions/{newest['id']}/diff")).json()
    assert diff["lines"] == [{"op": "del", "text": "Primeira"}, {"op": "add", "text": "Segunda"}]

    restored = (await client.post(f"/nodes/{node_id}/versions/{first['id']}/restore")).json()

    assert (restored["page"]["markdown"], restored["versions"]) == ("Primeira\n", 4)
    ids = [v["id"] for v in (await client.get(f"/nodes/{node_id}/versions")).json()]
    assert ids[1:] == [newest["id"], first["id"], empty["id"]]
