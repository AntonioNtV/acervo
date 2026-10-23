import io
import time
import zipfile
from pathlib import Path
from uuid import UUID

import httpx

from acervo.core import signing
from acervo.core.settings import Settings

PDF = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"


async def _kb(client: httpx.AsyncClient) -> str:
    kb_id: str = (await client.post("/v1/kbs", json={"name": "Seguros · Operação"})).json()["id"]
    return kb_id


async def _node(client: httpx.AsyncClient, kb_id: str, kind: str, title: str, parent_id: str | None = None) -> str:
    response = await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": kind, "title": title, "parent_id": parent_id})
    assert response.status_code == 201, response.text
    node_id: str = response.json()["id"]
    return node_id


async def _type(client: httpx.AsyncClient, node_id: str, markdown: str) -> None:
    revision = (await client.get(f"/v1/pages/{node_id}")).json()["revision"]
    response = await client.put(f"/v1/pages/{node_id}/text", json={"markdown": markdown, "revision": revision})
    assert response.status_code == 200, response.text


async def _upload(client: httpx.AsyncClient, kb_id: str, parent_id: str, name: str) -> str:
    with PDF.open("rb") as source:
        files = {"file": (name, source, "application/pdf")}
        response = await client.post(f"/v1/kbs/{kb_id}/files", data={"parent_id": parent_id}, files=files)
    assert response.status_code == 201, response.text
    node_id: str = response.json()["id"]
    return node_id


async def _export(client: httpx.AsyncClient, node_id: str) -> httpx.Response:
    """Downloads the zip by its signed link, without the key."""
    link = await client.post(f"/v1/nodes/{node_id}/export/link")
    assert link.status_code == 200, link.text
    key = client.headers.pop("X-API-Key")
    try:
        return await client.get(link.json()["url"])
    finally:
        client.headers["X-API-Key"] = key


async def test_zip_holds_pages_sub_pages_and_files(client: httpx.AsyncClient) -> None:
    kb_id = await _kb(client)
    page = await _node(client, kb_id, "page", "A")
    sub_page = await _node(client, kb_id, "page", "A1", page)
    await _upload(client, kb_id, page, "Condições.pdf")
    text = "# A\n\nVeja a [[A1]] — çã\r\n"
    await _type(client, page, text)
    await _type(client, sub_page, "Sub\n")

    response = await _export(client, page)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''A.zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.namelist() == ["A.md", "A/A1.md", "A/Condições.pdf"]
    assert archive.read("A.md") == text.encode()
    assert archive.read("A/A1.md") == b"Sub\n"
    assert archive.read("A/Condições.pdf") == PDF.read_bytes()


async def test_names_are_sanitized_and_deduplicated(client: httpx.AsyncClient) -> None:
    kb_id = await _kb(client)
    folder = await _node(client, kb_id, "folder", "Seguros/Auto: 2026")
    await _node(client, kb_id, "page", "Relatório", folder)
    await _node(client, kb_id, "folder", "relatório", folder)
    await _upload(client, kb_id, folder, "Relatório.md")
    await _node(client, kb_id, "folder", "Vazia", folder)

    response = await _export(client, folder)

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''Seguros_Auto_%202026.zip"
    assert zipfile.ZipFile(io.BytesIO(response.content)).namelist() == [
        "Seguros_Auto_ 2026/",
        "Seguros_Auto_ 2026/Relatório.md",
        "Seguros_Auto_ 2026/relatório (2)/",
        "Seguros_Auto_ 2026/Relatório (2).md",
        "Seguros_Auto_ 2026/Vazia/",
    ]


async def test_a_file_and_a_folder_of_the_same_name_do_not_clash(client: httpx.AsyncClient) -> None:
    kb_id = await _kb(client)
    folder = await _node(client, kb_id, "folder", "Residencial")
    await _upload(client, kb_id, folder, "Sinistro")
    await _node(client, kb_id, "folder", "sinistro", folder)
    page = await _node(client, kb_id, "page", "SINISTRO", folder)
    await _node(client, kb_id, "page", "Aviso", page)

    response = await _export(client, folder)

    assert response.status_code == 200, response.text
    assert zipfile.ZipFile(io.BytesIO(response.content)).namelist() == [
        "Residencial/",
        "Residencial/Sinistro",
        "Residencial/sinistro (2)/",
        "Residencial/SINISTRO (3).md",
        "Residencial/SINISTRO (3)/Aviso.md",
    ]


async def test_bad_signature_is_401(client: httpx.AsyncClient, test_settings: Settings) -> None:
    kb_id = await _kb(client)
    page = await _node(client, kb_id, "page", "A")
    secret = test_settings.api_key.get_secret_value()
    expires = int(time.time()) + signing.LINK_SECONDS
    del client.headers["X-API-Key"]

    signed = [
        (expires, "0" * 64),
        (expires, signing.sign(secret, "file", UUID(page), None, expires)),
        (expires - 120, signing.sign(secret, "export", UUID(page), None, expires - 120)),
    ]

    responses = [
        *[await client.get(f"/v1/nodes/{page}/export", params={"expires": e, "signature": s}) for e, s in signed],
        await client.post(f"/v1/nodes/{page}/export/link"),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(401, "unauthorized")] * 4


async def test_a_file_cannot_be_exported(client: httpx.AsyncClient) -> None:
    kb_id = await _kb(client)
    folder = await _node(client, kb_id, "folder", "Residencial")
    file = await _upload(client, kb_id, folder, "Condições.pdf")

    responses = [
        await client.post(f"/v1/nodes/{file}/export/link"),
        await client.get(f"/v1/nodes/{file}/export"),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(422, "validation")] * 2
