from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models import PageDraft, PageVersion


async def _page(client: httpx.AsyncClient, title: str = "Emissão de apólice") -> tuple[str, str]:
    kb_id: str = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    response = await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": title})
    assert response.status_code == 201, response.text
    node_id: str = response.json()["id"]
    return kb_id, node_id


async def _base(client: httpx.AsyncClient, node_id: str) -> str:
    version_id: str = (await client.get(f"/v1/pages/{node_id}")).json()["version_id"]
    return version_id


async def _save(client: httpx.AsyncClient, node_id: str, markdown: str) -> dict[str, Any]:
    body = {"markdown": markdown, "base_version_id": await _base(client, node_id)}
    response = await client.put(f"/v1/pages/{node_id}", json=body)
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def _versions(client: httpx.AsyncClient, node_id: str) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = (await client.get(f"/v1/pages/{node_id}/versions")).json()
    return versions


async def test_create_page_has_version_1(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)

    node = (await client.get(f"/v1/nodes/{node_id}")).json()

    assert (node["kind"], node["path"], node["versions"], node["file"]) == ("page", "Emissão de apólice", 1, None)
    assert (node["page"]["markdown"], node["page"]["draft"], node["page"]["sections"]) == ("", None, [])
    assert (await client.get(f"/v1/pages/{node_id}")).json() == node["page"]
    [version] = await _versions(client, node_id)
    assert (version["id"], version["author"]) == (node["page"]["version_id"], "user")


async def test_save_stale_is_409_stale_page_with_diff(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    opened = await _base(client, node_id)
    saved = await _save(client, node_id, "## Prazo\n\nCinco dias.\n")

    stale = await client.put(f"/v1/pages/{node_id}", json={"markdown": "Minha versão\n", "base_version_id": opened})

    assert (stale.status_code, stale.json()["error"]) == (409, "stale_page")
    details = stale.json()["details"]
    assert (details["current_version_id"], details["markdown"]) == (saved["id"], "## Prazo\n\nCinco dias.\n")
    assert {"op": "add", "text": "## Prazo"} in details["diff"]
    forced = await client.put(
        f"/v1/pages/{node_id}", json={"markdown": "Minha versão\n", "base_version_id": opened, "force": True}
    )
    assert forced.status_code == 200
    assert len(await _versions(client, node_id)) == 3


async def test_draft_round_trip(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    base = await _base(client, node_id)

    put = await client.put(f"/v1/pages/{node_id}/draft", json={"markdown": "Rascunho\n", "base_version_id": base})
    assert put.json()["markdown"] == "Rascunho\n"
    draft = (await client.get(f"/v1/pages/{node_id}")).json()["draft"]
    assert (draft["markdown"], draft["base_version_id"]) == ("Rascunho\n", base)

    assert (await client.delete(f"/v1/pages/{node_id}/draft")).status_code == 204
    node = (await client.get(f"/v1/nodes/{node_id}")).json()
    assert (node["page"]["draft"], node["versions"]) == (None, 1)


async def test_rename_fixes_links(client: httpx.AsyncClient) -> None:
    kb_id, emission = await _page(client)
    renewal = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Renovação"})).json()["id"]
    await _save(client, emission, "Antes da [[Renovação]] e da [[Vistoria]].\n")
    assert (await client.get(f"/v1/pages/{emission}")).json()["links"] == {"renovação": renewal, "vistoria": "missing"}

    renamed = await client.patch(f"/v1/nodes/{renewal}", json={"title": "Renovação anual"})

    assert renamed.json()["title"] == "Renovação anual"
    page = (await client.get(f"/v1/pages/{emission}")).json()
    assert page["markdown"] == "Antes da [[Renovação anual]] e da [[Vistoria]].\n"
    assert page["links"] == {"renovação anual": renewal, "vistoria": "missing"}
    assert [v["author"] for v in await _versions(client, emission)] == ["user"] * 3


async def test_restore_version(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    await _save(client, node_id, "Primeira\n")
    await _save(client, node_id, "Segunda\n")
    newest, first, empty = await _versions(client, node_id)

    diff = (await client.get(f"/v1/pages/{node_id}/versions/{newest['id']}/diff")).json()
    assert diff["lines"] == [{"op": "del", "text": "Primeira"}, {"op": "add", "text": "Segunda"}]

    restored = (await client.post(f"/v1/pages/{node_id}/versions/{first['id']}/restore")).json()

    assert restored["markdown"] == "Primeira\n"
    ids = [v["id"] for v in await _versions(client, node_id)]
    assert ids[0] == restored["version_id"]
    assert ids[1:] == [newest["id"], first["id"], empty["id"]]


async def test_history_has_no_text(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    await _save(client, node_id, "Primeira\n")

    versions = await _versions(client, node_id)

    assert [set(version) for version in versions] == [{"id", "author", "created_at"}] * 2


async def test_401_without_the_key(client: httpx.AsyncClient, session: AsyncSession) -> None:
    _, node_id = await _page(client)
    base = await _base(client, node_id)
    del client.headers["X-API-Key"]

    body = {"markdown": "Outra\n", "base_version_id": base}
    responses = [
        await client.get(f"/v1/pages/{node_id}"),
        await client.put(f"/v1/pages/{node_id}", json=body),
        await client.put(f"/v1/pages/{node_id}/draft", json=body),
        await client.get(f"/v1/nodes/{node_id}"),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(401, "unauthorized")] * 4
    assert await session.scalar(select(func.count()).where(PageVersion.node_id == node_id)) == 1
    assert await session.scalar(select(func.count()).where(PageDraft.node_id == node_id)) == 0
