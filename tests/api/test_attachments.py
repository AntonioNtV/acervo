import io
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI

from acervo.core.settings import Settings

MakeTree = Callable[..., Awaitable[Any]]
PHOTO = b"\xff\xd8\xff\xe0" + bytes(range(256)) * 4


async def _upload(client: httpx.AsyncClient, page: str, content: bytes, name: str = "foto.jpg") -> httpx.Response:
    return await client.post(f"/v1/pages/{page}/attachments", files={"file": (name, io.BytesIO(content))})


async def _open(client: httpx.AsyncClient, page: str, name: str = "foto.jpg") -> httpx.Response:
    link = await client.post(f"/v1/pages/{page}/attachments/{name}/link")
    if link.status_code != 200:
        return link
    return await client.get(link.json()["url"], headers={"Cookie": ""})


async def test_upload_link_raw_and_range(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md"]})
    page = str(tree["Residencial/Vistoria.md"].id)

    first = await _upload(client, page, PHOTO)
    second = await _upload(client, page, PHOTO, "../fotos/foto.jpg")
    raw = await _open(client, page)
    link = (await client.post(f"/v1/pages/{page}/attachments/foto.jpg/link")).json()["url"]
    other = await client.get(link.replace("foto.jpg", "foto-2.jpg"), headers={"Cookie": ""})
    ranged = await client.get(f"/v1/pages/{page}/attachments/foto-2.jpg/raw", headers={"Range": "bytes=4-7"})

    assert first.json() == {"name": "foto.jpg", "mime": "image/jpeg", "size": len(PHOTO)}
    assert second.json()["name"] == "foto-2.jpg"
    assert (raw.status_code, raw.content, raw.headers["content-type"]) == (200, PHOTO, "image/jpeg")
    assert raw.headers["content-disposition"] == "attachment; filename*=UTF-8''foto.jpg"
    assert raw.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert other.status_code == 404, "a link opens only the attachment it was signed for"
    assert (ranged.status_code, ranged.content) == (206, PHOTO[4:8])
    assert ranged.headers["content-range"] == f"bytes 4-7/{len(PHOTO)}"


async def test_too_large_or_not_a_page_is_422(
    client: httpx.AsyncClient, app: FastAPI, make_tree: MakeTree, test_settings: Settings
) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md", "CG 2026.pdf"]})
    app.state.settings = test_settings.model_copy(update={"attachment_max_bytes": len(PHOTO) - 1})

    too_large = await _upload(client, str(tree["Residencial/Vistoria.md"].id), PHOTO)
    folder = await _upload(client, str(tree["Residencial"].id), b"x")
    file = await _upload(client, str(tree["Residencial/CG 2026.pdf"].id), b"x")

    assert (too_large.status_code, too_large.json()["error"]) == (422, "attachment_too_large")
    assert [(r.status_code, r.json()["error"]) for r in (folder, file)] == [(422, "validation")] * 2


async def test_follows_the_page_to_the_trash_and_back(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md"]})
    page = str(tree["Residencial/Vistoria.md"].id)
    await _upload(client, page, PHOTO)

    await client.delete(f"/v1/nodes/{tree['Residencial'].id}")
    trashed = [await _open(client, page), await client.get(f"/v1/pages/{page}/attachments/foto.jpg/raw")]
    await client.post(f"/v1/nodes/{tree['Residencial'].id}/restore")
    restored = await _open(client, page)

    assert [response.status_code for response in trashed] == [404, 404]
    assert (restored.status_code, restored.content) == (200, PHOTO)


async def test_survives_a_move_to_another_base(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md"]})
    other = await make_tree({"Destino": None}, name="Porto")
    page = str(tree["Residencial/Vistoria.md"].id)
    await _upload(client, page, PHOTO)

    moved = await client.post(f"/v1/nodes/{page}/move", json={"kb_id": str(other.kb.id), "parent_id": None})
    raw = await _open(client, page)

    assert moved.status_code == 200, moved.text
    assert (raw.status_code, raw.content) == (200, PHOTO)


async def test_the_copy_of_a_page_opens_its_attachment(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md"]})
    page = str(tree["Residencial/Vistoria.md"].id)
    await _upload(client, page, PHOTO)

    copy = (await client.post(f"/v1/nodes/{page}/duplicate")).json()["id"]
    raw = await _open(client, copy)

    assert (raw.status_code, raw.content) == (200, PHOTO)


async def test_is_not_a_node(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Vistoria.md"]})
    page = str(tree["Residencial/Vistoria.md"].id)
    await _upload(client, page, PHOTO)

    children = await client.get(f"/v1/kbs/{tree.kb.id}/children", params={"parent_id": page})
    search = await client.get(f"/v1/kbs/{tree.kb.id}/search", params={"q": "foto"})

    assert (children.json(), search.json()) == ([], [])
