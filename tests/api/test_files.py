import hashlib
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.settings import Settings
from acervo.repositories.kb import KbRepository
from acervo.schemas.kb import KbUpdate

PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"
SIMPLE = PDFS / "simple.pdf"
PROTECTED = PDFS / "protected.pdf"

MakeTree = Callable[..., Awaitable[Any]]


async def _folder(make_tree: MakeTree) -> tuple[str, str]:
    tree = await make_tree({"Residencial": None})
    return str(tree.kb.id), str(tree["Residencial"].id)


async def _upload(
    client: httpx.AsyncClient,
    kb_id: str,
    parent_id: str | None,
    path: Path,
    name: str = "Condições Gerais 2026.pdf",
) -> httpx.Response:
    with path.open("rb") as source:
        data = {"parent_id": parent_id} if parent_id else {}
        return await client.post(f"/v1/kbs/{kb_id}/files", data=data, files={"file": (name, source, "application/pdf")})


async def test_upload_then_raw_returns_same_bytes(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)

    uploaded = await _upload(client, kb_id, folder, SIMPLE)

    assert uploaded.status_code == 201
    node = uploaded.json()
    assert (node["path"], node["file"]["pages"], node["file"]["protected"], node["versions"]) == (
        "Residencial/Condições Gerais 2026.pdf",
        3,
        False,
        1,
    )
    raw = await client.get(f"/v1/files/{node['id']}/raw")
    assert hashlib.sha256(raw.content).hexdigest() == hashlib.sha256(SIMPLE.read_bytes()).hexdigest()
    assert raw.headers["content-type"] == "application/pdf"
    assert raw.headers["content-disposition"] == "attachment; filename*=UTF-8''Condi%C3%A7%C3%B5es%20Gerais%202026.pdf"


async def test_range_request(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]
    content = SIMPLE.read_bytes()

    first = await client.get(f"/v1/files/{node_id}/raw", headers={"Range": "bytes=0-99"})
    tail = await client.get(f"/v1/files/{node_id}/raw", headers={"Range": "bytes=-10"})
    outside = await client.get(f"/v1/files/{node_id}/raw", headers={"Range": f"bytes={len(content)}-"})

    assert (first.status_code, first.content) == (206, content[:100])
    assert first.headers["content-range"] == f"bytes 0-99/{len(content)}"
    assert (tail.status_code, tail.content) == (206, content[-10:])
    assert (outside.status_code, outside.headers["content-range"]) == (416, f"bytes */{len(content)}")


async def test_open_ended_range_streams(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]
    content = SIMPLE.read_bytes()

    rest = await client.get(f"/v1/files/{node_id}/raw", headers={"Range": "bytes=100-"})

    assert (rest.status_code, rest.content) == (206, content[100:])
    assert rest.headers["content-range"] == f"bytes 100-{len(content) - 1}/{len(content)}"
    assert rest.headers["content-length"] == str(len(content) - 100)


async def test_duplicate_is_409_duplicate_with_details(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    first = (await _upload(client, kb_id, folder, SIMPLE)).json()

    again = await _upload(client, kb_id, None, SIMPLE, "Outro nome.pdf")

    assert again.status_code == 409
    assert again.json() == {
        "error": "duplicate",
        "message": "já está em Residencial/Condições Gerais 2026.pdf",
        "details": {"node_id": first["id"], "path": first["path"], "trashed": False, "history": False},
    }


async def test_upload_to_unknown_base_is_404(
    client: httpx.AsyncClient, make_tree: MakeTree, session: AsyncSession
) -> None:
    trashed = (await make_tree({}, name="Antiga")).kb.id
    await KbRepository(session).update(trashed, KbUpdate(deleted_at=datetime.now(UTC)))

    for kb_id in (uuid.uuid4(), trashed):
        response = await _upload(client, str(kb_id), None, SIMPLE)
        assert (response.status_code, response.json()["error"]) == (404, "not_found")


async def test_replace_with_same_content_is_409_same_file(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]

    with SIMPLE.open("rb") as source:
        response = await client.post(f"/v1/nodes/{node_id}/file", files={"file": ("novo.pdf", source)})

    assert (response.status_code, response.json()["error"]) == (409, "same_file")


async def test_replace_and_restore(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]

    with PROTECTED.open("rb") as source:
        replaced = await client.post(f"/v1/nodes/{node_id}/file", files={"file": ("novo.pdf", source)})

    assert (replaced.json()["file"]["protected"], replaced.json()["versions"]) == (True, 2)
    [old] = (await client.get(f"/v1/files/{node_id}/versions")).json()
    old_raw = await client.get(f"/v1/files/{node_id}/raw", params={"version_id": old["id"]})
    assert old_raw.content == SIMPLE.read_bytes()

    restored = (await client.post(f"/v1/files/{node_id}/versions/{old['id']}/restore")).json()

    assert (restored["file"]["protected"], restored["versions"]) == (False, 3)
    assert (await client.get(f"/v1/files/{node_id}/raw")).content == SIMPLE.read_bytes()


async def test_raw_exposes_range_headers_to_the_web_origin(
    client: httpx.AsyncClient, make_tree: MakeTree, test_settings: Settings
) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]

    origin = test_settings.cors_origins[0]
    raw = await client.get(f"/v1/files/{node_id}/raw", headers={"Origin": origin, "Range": "bytes=0-9"})

    exposed = {name.strip().lower() for name in raw.headers["access-control-expose-headers"].split(",")}
    assert {"content-range", "accept-ranges", "content-disposition"} <= exposed


async def test_file_routes_without_the_key_are_401(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    kb_id, folder = await _folder(make_tree)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]
    del client.headers["X-API-Key"]

    responses = [
        await _upload(client, kb_id, folder, PROTECTED, "Outro.pdf"),
        await client.get(f"/v1/files/{node_id}/raw"),
        await client.get(f"/v1/files/{node_id}/versions"),
    ]

    assert [(response.status_code, response.json()["error"]) for response in responses] == [(401, "unauthorized")] * 3
