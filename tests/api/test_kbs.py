from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx

from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord

MakeTree = Callable[..., Awaitable[Any]]


async def _create(client: httpx.AsyncClient, **body: Any) -> dict[str, Any]:
    response = await client.post("/v1/kbs", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def test_create_list_counts_rename_trash_restore(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    created = await _create(client, name="  Seguros · Operação  ", description="Apólices")
    assert (created["name"], created["deleted_at"]) == ("Seguros · Operação", None)
    kb_id = created["id"]
    folder = (await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "folder", "title": "Bradesco"})).json()
    for kind, title in [("page", "Emissão de apólice"), ("page", "Renovação"), ("folder", "Antigos")]:
        await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": kind, "title": title, "parent_id": folder["id"]})
    await client.post(f"/v1/kbs/{kb_id}/nodes", json={"kind": "page", "title": "Sinistro"})
    await client.delete(f"/v1/nodes/{folder['id']}")
    other = await make_tree({"Itaú": ["Tabela.md", "CG 2026.pdf", "Planilha.xlsx"]}, name="Jurídico")

    listed = {kb["id"]: kb for kb in (await client.get("/v1/kbs")).json()}
    assert (listed[kb_id]["pages"], listed[kb_id]["files"]) == (1, 0)
    assert (listed[str(other.kb.id)]["pages"], listed[str(other.kb.id)]["files"]) == (1, 2)
    assert listed[kb_id]["last_edit"]

    renamed = await client.patch(f"/v1/kbs/{kb_id}", json={"name": "Seguros", "description": " Sinistros "})
    assert (renamed.json()["name"], renamed.json()["description"]) == ("Seguros", "Sinistros")
    blank = await client.patch(f"/v1/kbs/{kb_id}", json={"name": "   "})
    assert (blank.status_code, blank.json()["error"]) == (422, "validation")

    trashed = await client.delete(f"/v1/kbs/{kb_id}")
    assert trashed.json()["deleted_at"] is not None
    assert [kb["id"] for kb in (await client.get("/v1/kbs")).json()] == [str(other.kb.id)]
    assert [kb["id"] for kb in (await client.get("/v1/kbs/trash")).json()] == [kb_id]
    gone = await client.patch(f"/v1/kbs/{kb_id}", json={"name": "Outro"})
    assert (gone.status_code, gone.json()["error"]) == (404, "not_found")

    restored = await client.post(f"/v1/kbs/{kb_id}/restore")
    assert restored.json()["deleted_at"] is None
    summaries = {kb["id"]: kb for kb in (await client.get("/v1/kbs")).json()}
    assert (summaries[kb_id]["name"], summaries[kb_id]["pages"]) == ("Seguros", 1)
    assert (await client.get("/v1/kbs/trash")).json() == []
    again = await client.post(f"/v1/kbs/{kb_id}/restore")
    assert (again.status_code, again.json()["error"]) == (404, "not_found")


async def test_name_filter_ignores_case_and_accents(client: httpx.AsyncClient) -> None:
    seguros = await _create(client, name="Seguros · Operação")
    juridico = await _create(client, name="Jurídico")

    assert [kb["id"] for kb in (await client.get("/v1/kbs", params={"q": "JURIDICO"})).json()] == [juridico["id"]]
    assert [kb["id"] for kb in (await client.get("/v1/kbs", params={"q": "operacao"})).json()] == [seguros["id"]]
    assert (await client.get("/v1/kbs", params={"q": "100%"})).json() == []


async def test_base_icon_is_set_and_cleared(client: httpx.AsyncClient) -> None:
    created = await _create(client, name="Seguros")
    assert created["icon"] is None

    set_ = await client.patch(f"/v1/kbs/{created['id']}", json={"icon": "🛡️"})
    renamed = await client.patch(f"/v1/kbs/{created['id']}", json={"name": "Seguros · Operação"})
    invalid = await client.patch(f"/v1/kbs/{created['id']}", json={"icon": "ab"})
    listed = (await client.get("/v1/kbs")).json()
    cleared = await client.patch(f"/v1/kbs/{created['id']}", json={"icon": None})

    assert (set_.status_code, set_.json()["icon"]) == (200, "🛡️")
    assert renamed.json()["icon"] == "🛡️"
    assert (invalid.status_code, invalid.json()["error"]) == (422, "validation")
    assert [kb["icon"] for kb in listed] == ["🛡️"]
    assert (cleared.status_code, cleared.json()["icon"]) == (200, None)


async def test_base_access_general_and_members(
    client: httpx.AsyncClient,
    make_account: Callable[..., Awaitable[AccountRead]],
    make_organization: Callable[..., Awaitable[OrganizationRecord]],
) -> None:
    olga = await make_account(email="olga@example.com", name="Olga")
    bia = await make_account(email="bia@example.com", name="Bia")
    dani = await make_account(email="dani@example.com", name="Dani")
    me = (await client.get("/v1/account")).json()["id"]
    team = await make_organization(olga.id, members={UUID(me): "admin", bia.id: "member"})
    kb = await _create(client, name="Sinistros", organization_id=str(team.id))

    restricted = await client.put(f"/v1/kbs/{kb['id']}/access", json={"general_access": "none"})
    added = await client.put(f"/v1/kbs/{kb['id']}/members/{bia.id}", json={"role": "reader"})
    outsider = await client.put(f"/v1/kbs/{kb['id']}/members/{dani.id}", json={"role": "reader"})
    listed = (await client.get("/v1/kbs", params={"organization_id": str(team.id)})).json()
    removed = await client.delete(f"/v1/kbs/{kb['id']}/members/{bia.id}")
    again = await client.delete(f"/v1/kbs/{kb['id']}/members/{bia.id}")

    assert (kb["general_access"], kb["my_role"]) == ("editor", "admin")
    assert restricted.json()["general_access"] == "none"
    assert [(m["name"], m["role"]) for m in added.json()["members"]] == [("Ana", "admin"), ("Bia", "reader")]
    assert (outsider.status_code, outsider.json()["error"]) == (403, "forbidden")
    assert [(b["id"], b["my_role"]) for b in listed] == [(kb["id"], "admin")]
    assert [m["name"] for m in removed.json()["members"]] == ["Ana"]
    assert (again.status_code, again.json()["error"]) == (404, "not_found")
    assert (await client.get(f"/v1/kbs/{kb['id']}/access")).json() == removed.json()
