from typing import Any
from uuid import uuid4

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


async def _revision(client: httpx.AsyncClient, node_id: str) -> int:
    revision: int = (await client.get(f"/v1/pages/{node_id}")).json()["revision"]
    return revision


async def _type(client: httpx.AsyncClient, node_id: str, markdown: str) -> dict[str, Any]:
    body = {"markdown": markdown, "revision": await _revision(client, node_id)}
    response = await client.put(f"/v1/pages/{node_id}/text", json=body)
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def _save(client: httpx.AsyncClient, node_id: str, markdown: str) -> None:
    """Types `markdown` and leaves the page: one version of it."""
    await _type(client, node_id, markdown)
    assert (await client.post(f"/v1/pages/{node_id}/leave")).status_code == 204


async def _versions(client: httpx.AsyncClient, node_id: str) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = (await client.get(f"/v1/pages/{node_id}/versions")).json()
    return versions


async def test_create_page_has_version_1(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)

    node = (await client.get(f"/v1/nodes/{node_id}")).json()

    assert (node["kind"], node["path"], node["versions"], node["file"]) == ("page", "Emissão de apólice", 1, None)
    assert (node["page"]["markdown"], node["page"]["revision"], node["page"]["sections"]) == ("", 0, [])
    assert (await client.get(f"/v1/pages/{node_id}")).json() == node["page"]
    [version] = await _versions(client, node_id)
    assert (version["id"], version["author"]) == (node["page"]["version_id"], "user")


async def test_text_put_and_get_round_trip(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)

    saved = await _type(client, node_id, "## Prazo\n\nCinco dias.\n")

    page = (await client.get(f"/v1/pages/{node_id}")).json()
    assert (page["markdown"], page["revision"], page["saved_at"]) == (
        "## Prazo\n\nCinco dias.\n",
        saved["revision"],
        saved["saved_at"],
    )
    assert page["sections"] == [{"anchor": "prazo", "heading": "Prazo"}]
    assert (await client.get(f"/v1/nodes/{node_id}")).json()["versions"] == 1


async def test_stale_revision_is_409_stale_page(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    opened = await _revision(client, node_id)
    saved = await _type(client, node_id, "Primeira aba\n")

    stale = await client.put(f"/v1/pages/{node_id}/text", json={"markdown": "Segunda aba\n", "revision": opened})

    assert (stale.status_code, stale.json()["error"]) == (409, "stale_page")
    assert stale.json()["details"] == {"markdown": "Primeira aba\n", "revision": saved["revision"]}
    assert (await client.get(f"/v1/nodes/{node_id}")).json()["versions"] == 2


async def test_leave_route(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    await _type(client, node_id, "Antes de sair\n")

    left = await client.post(f"/v1/pages/{node_id}/leave")

    assert left.status_code == 204
    page = (await client.get(f"/v1/pages/{node_id}")).json()
    assert (await client.get(f"/v1/nodes/{node_id}")).json()["versions"] == 2
    diff = (await client.get(f"/v1/pages/{node_id}/versions/{page['version_id']}/diff")).json()
    assert diff["lines"] == [{"op": "add", "text": "Antes de sair"}]
    assert (await client.post(f"/v1/pages/{uuid4()}/leave")).json()["error"] == "not_found"


async def test_old_save_and_draft_routes_are_gone(client: httpx.AsyncClient) -> None:
    _, node_id = await _page(client)
    body = {"markdown": "Velha\n", "base_version_id": (await client.get(f"/v1/pages/{node_id}")).json()["version_id"]}

    responses = [
        await client.put(f"/v1/pages/{node_id}", json=body),
        await client.put(f"/v1/pages/{node_id}/draft", json=body),
        await client.delete(f"/v1/pages/{node_id}/draft"),
    ]

    assert [r.status_code for r in responses] == [405, 404, 404]
    assert (await client.get(f"/v1/pages/{node_id}")).json()["markdown"] == ""


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

    assert [set(version) for version in versions] == [
        {"id", "author", "created_at", "edit_started_at", "edit_ended_at"}
    ] * 2


async def test_401_without_the_key(client: httpx.AsyncClient, session: AsyncSession) -> None:
    _, node_id = await _page(client)
    del client.headers["X-API-Key"]

    responses = [
        await client.get(f"/v1/pages/{node_id}"),
        await client.put(f"/v1/pages/{node_id}/text", json={"markdown": "Outra\n", "revision": 0}),
        await client.post(f"/v1/pages/{node_id}/leave"),
        await client.get(f"/v1/nodes/{node_id}"),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(401, "unauthorized")] * 4
    assert await session.scalar(select(func.count()).where(PageVersion.node_id == node_id)) == 1
    assert await session.scalar(select(func.count()).where(PageDraft.node_id == node_id)) == 0


async def test_mentions_list_linking_pages_with_the_line(client: httpx.AsyncClient) -> None:
    kb_id, emission = await _page(client)
    folder = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "folder", "title": "Auto"})).json()["id"]
    body = {"kind": "page", "title": "Vistoria", "parent_id": folder}
    inspection = (await client.post(f"/v1/kbs/{kb_id}/nodes", json=body)).json()["id"]
    renewal = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Renovação"})).json()["id"]
    long_line = "Veja " + "muito " * 50 + "[[emissão de  apólice]]"
    await _type(client, renewal, "# Renovação\n\n  Antes, a [[Emissão de apólice]].  \nDe novo: [[Emissão de apólice]]")
    await _type(client, inspection, f"{long_line}\n")
    await _type(client, emission, "Sem links para si.\n")

    response = await client.get(f"/v1/pages/{emission}/mentions")

    assert response.status_code == 200, response.text
    mentions = response.json()
    assert [(m["node"]["id"], m["node"]["path"], m["line"]) for m in mentions] == [
        (inspection, "Auto/Vistoria", long_line[:200]),
        (renewal, "Renovação", "Antes, a [[Emissão de apólice]]."),
    ]


async def test_no_mentions_is_empty(client: httpx.AsyncClient) -> None:
    kb_id, emission = await _page(client)
    renewal = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Renovação"})).json()["id"]
    await _type(client, renewal, "Fala de Emissão de apólice sem link, e da [[Vistoria]].\n")

    response = await client.get(f"/v1/pages/{emission}/mentions")

    assert (response.status_code, response.json()) == (200, [])


async def test_nul_is_stripped_from_page_text_titles_and_base_names(client: httpx.AsyncClient) -> None:
    kb = (await client.post("/v1/kbs", json={"name": "Seg\x00uros"})).json()
    response = await client.post(f"/v1/kbs/{kb['id']}/nodes", json={"kind": "page", "title": "Pra\x00zos"})
    assert response.status_code == 201, response.text
    node_id = response.json()["id"]

    await _type(client, node_id, "Cinco\x00 dias.\n")

    renamed = await client.patch(f"/v1/nodes/{node_id}", json={"title": "Novos\x00 prazos"})
    assert renamed.status_code == 200, renamed.text
    page = (await client.get(f"/v1/nodes/{node_id}")).json()
    assert (kb["name"], page["title"], page["page"]["markdown"]) == ("Seguros", "Novos prazos", "Cinco dias.\n")
