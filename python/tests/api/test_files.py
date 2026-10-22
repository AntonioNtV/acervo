import hashlib
from pathlib import Path

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


PDFS = Path(__file__).parent.parent / "fixtures" / "pdfs"
SIMPLE = PDFS / "simple.pdf"
PROTECTED = PDFS / "protected.pdf"


async def _folder(client) -> tuple[str, str]:
    kb_id = (await client.post("/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    response = await client.post(f"/kbs/{kb_id}/nodes", json={"kind": "folder", "title": "Residencial"})
    return kb_id, response.json()["id"]


async def _upload(client, kb_id: str, parent_id: str | None, path: Path, name: str = "Condições Gerais 2026.pdf"):
    with path.open("rb") as source:
        data = {"parent_id": parent_id} if parent_id else {}
        return await client.post(f"/kbs/{kb_id}/files", data=data, files={"file": (name, source, "application/pdf")})


async def test_upload_then_raw_returns_same_bytes(client) -> None:
    kb_id, folder = await _folder(client)

    uploaded = await _upload(client, kb_id, folder, SIMPLE)

    assert uploaded.status_code == 201
    node = uploaded.json()
    assert (node["path"], node["file"]["pages"], node["file"]["protected"]) == (
        "Residencial/Condições Gerais 2026.pdf",
        3,
        False,
    )
    raw = await client.get(f"/files/{node['id']}/raw")
    assert hashlib.sha256(raw.content).hexdigest() == hashlib.sha256(SIMPLE.read_bytes()).hexdigest()
    assert raw.headers["content-type"] == "application/pdf"
    assert raw.headers["content-disposition"] == "attachment; filename*=UTF-8''Condi%C3%A7%C3%B5es%20Gerais%202026.pdf"


async def test_range_request(client) -> None:
    kb_id, folder = await _folder(client)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]
    content = SIMPLE.read_bytes()

    first = await client.get(f"/files/{node_id}/raw", headers={"Range": "bytes=0-99"})
    tail = await client.get(f"/files/{node_id}/raw", headers={"Range": "bytes=-10"})
    outside = await client.get(f"/files/{node_id}/raw", headers={"Range": f"bytes={len(content)}-"})

    assert (first.status_code, first.content) == (206, content[:100])
    assert first.headers["content-range"] == f"bytes 0-99/{len(content)}"
    assert (tail.status_code, tail.content) == (206, content[-10:])
    assert (outside.status_code, outside.headers["content-range"]) == (416, f"bytes */{len(content)}")


async def test_duplicate_is_409_with_path(client) -> None:
    kb_id, folder = await _folder(client)
    first = (await _upload(client, kb_id, folder, SIMPLE)).json()

    again = await _upload(client, kb_id, None, SIMPLE, "Outro nome.pdf")

    assert again.status_code == 409
    body = again.json()
    assert body["message"] == "já está em Residencial/Condições Gerais 2026.pdf"
    assert body["detail"] == {"node_id": first["id"], "path": first["path"], "trashed": False}
    assert [n["title"] for n in (await client.get(f"/kbs/{kb_id}/children")).json()] == ["Residencial"]


async def test_replace_and_restore(client) -> None:
    kb_id, folder = await _folder(client)
    node_id = (await _upload(client, kb_id, folder, SIMPLE)).json()["id"]

    with PROTECTED.open("rb") as source:
        replaced = await client.post(f"/nodes/{node_id}/file", files={"file": ("novo.pdf", source)})

    assert (replaced.json()["file"]["protected"], replaced.json()["versions"]) == (True, 2)
    [tree_node] = (await client.get(f"/kbs/{kb_id}/children", params={"parent_id": folder})).json()
    assert tree_node["protected"] is True
    [old] = (await client.get(f"/nodes/{node_id}/versions")).json()
    old_raw = await client.get(f"/files/{node_id}/raw", params={"version_id": old["id"]})
    assert old_raw.content == SIMPLE.read_bytes()

    restored = (await client.post(f"/nodes/{node_id}/versions/{old['id']}/restore")).json()

    assert (restored["file"]["protected"], restored["versions"]) == (False, 3)
    assert (await client.get(f"/files/{node_id}/raw")).content == SIMPLE.read_bytes()
