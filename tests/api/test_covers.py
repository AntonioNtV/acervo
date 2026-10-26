import hashlib
import io
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from acervo.core.settings import Settings

FIXTURES = Path(__file__).parent.parent / "fixtures"
PHOTO = FIXTURES / "files" / "photo.png"
PDF = FIXTURES / "pdfs" / "simple.pdf"

MakeTree = Callable[..., Awaitable[Any]]


async def _upload(client: httpx.AsyncClient, node_id: str, content: bytes, name: str = "capa.png") -> httpx.Response:
    return await client.post(f"/v1/nodes/{node_id}/cover", files={"file": (name, io.BytesIO(content))})


async def test_upload_and_open_by_link(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Renovação.md"]})
    page = str(tree["Residencial/Renovação.md"].id)

    uploaded = await _upload(client, page, PHOTO.read_bytes())
    link = await client.post(f"/v1/nodes/{page}/cover/link")
    raw = await client.get(link.json()["url"], headers={"Cookie": ""})

    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["cover"] == f"image:{hashlib.sha256(PHOTO.read_bytes()).hexdigest()}"
    assert (raw.status_code, raw.content, raw.headers["content-type"]) == (200, PHOTO.read_bytes(), "image/png")
    assert raw.headers["cache-control"] == "private, max-age=31536000, immutable"


async def test_wrong_type_or_too_big_is_422(
    client: httpx.AsyncClient, make_tree: MakeTree, test_settings: Settings
) -> None:
    tree = await make_tree({"Residencial": ["Renovação.md", "CG 2026.pdf"]})
    page = str(tree["Residencial/Renovação.md"].id)
    file = str(tree["Residencial/CG 2026.pdf"].id)
    too_big = PHOTO.read_bytes()[:8] + bytes(test_settings.cover_max_bytes + 1024 * 1024)

    responses = [
        await _upload(client, page, PDF.read_bytes(), "capa.pdf"),
        await _upload(client, page, too_big),
        await _upload(client, file, PHOTO.read_bytes()),
    ]

    assert [(response.status_code, response.json()["error"]) for response in responses] == [(422, "validation")] * 3
    assert (await client.get(f"/v1/nodes/{page}")).json()["cover"] is None


async def test_cover_survives_a_move_to_another_base(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": ["Renovação.md"]})
    other = await make_tree({"Destino": None}, name="Porto")
    page = str(tree["Residencial/Renovação.md"].id)
    await _upload(client, page, PHOTO.read_bytes())

    moved = await client.post(f"/v1/nodes/{page}/move", json={"kb_id": str(other.kb.id), "parent_id": None})
    link = await client.post(f"/v1/nodes/{page}/cover/link")
    raw = await client.get(link.json()["url"])

    assert moved.status_code == 200, moved.text
    assert (raw.status_code, raw.content) == (200, PHOTO.read_bytes())


async def test_no_image_cover_is_404(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Residencial": None, "Auto": None})
    folder = str(tree["Residencial"].id)
    gallery = str(tree["Auto"].id)
    await client.patch(f"/v1/nodes/{gallery}", json={"cover": "gallery:mar"})

    responses = [await client.post(f"/v1/nodes/{node}/cover/link") for node in (folder, gallery)]
    raw = await client.get(f"/v1/nodes/{folder}/cover/raw")

    assert [(response.status_code, response.json()["error"]) for response in responses] == [(404, "not_found")] * 2
    assert raw.status_code == 404
