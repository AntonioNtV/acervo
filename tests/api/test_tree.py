import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models import File, Node

MakeTree = Callable[..., Awaitable[Any]]


async def _node(client: httpx.AsyncClient, kb_id: Any, title: str, kind: str = "page", parent_id: Any = None) -> str:
    body = {"kind": kind, "title": title, "parent_id": parent_id and str(parent_id)}
    response = await client.post(f"/v1/kbs/{kb_id}/nodes", json=body)
    assert response.status_code == 201, response.text
    node_id: str = response.json()["id"]
    return node_id


async def _children(client: httpx.AsyncClient, kb_id: Any, parent_id: Any = None) -> list[dict[str, Any]]:
    params = {"parent_id": str(parent_id)} if parent_id else {}
    response = await client.get(f"/v1/kbs/{kb_id}/children", params=params)
    assert response.status_code == 200, response.text
    children: list[dict[str, Any]] = response.json()
    return children


async def _titles(client: httpx.AsyncClient, kb_id: Any, parent_id: Any = None) -> list[str]:
    return [node["title"] for node in await _children(client, kb_id, parent_id)]


async def _move(client: httpx.AsyncClient, node_id: Any, parent_id: Any, before_id: Any = None) -> httpx.Response:
    body = {"parent_id": parent_id and str(parent_id), "before_id": before_id and str(before_id)}
    return await client.post(f"/v1/nodes/{node_id}/move", json=body)


async def test_children_follow_the_order_the_person_set(
    client: httpx.AsyncClient, session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "B.md", "C.md", "CG 2026.pdf"], "Porto": None})
    bradesco = tree["Bradesco"].id
    pdf = await session.scalar(select(File).where(File.node_id == tree["Bradesco/CG 2026.pdf"].id))
    assert pdf is not None
    pdf.protected = True
    await session.flush()

    await _move(client, tree["Bradesco/C.md"].id, bradesco, before_id=tree["Bradesco/A.md"].id)
    await _move(client, tree["Bradesco/A.md"].id, bradesco)
    new = await _node(client, tree.kb.id, "D", parent_id=bradesco)
    await _move(client, new, bradesco, before_id=tree["Bradesco/B.md"].id)
    folder = await _node(client, tree.kb.id, "B", "folder", bradesco)

    children = await _children(client, tree.kb.id, bradesco)
    assert [(node["kind"], node["title"]) for node in children] == [
        ("page", "C"),
        ("page", "D"),
        ("page", "B"),
        ("file", "CG 2026.pdf"),
        ("page", "A"),
        ("folder", "B"),
    ]
    assert [node["title"] for node in children if node["protected"]] == ["CG 2026.pdf"]
    assert children[-1]["id"] == folder
    assert await _titles(client, tree.kb.id) == ["Bradesco", "Porto"]


async def test_move_between_siblings_changes_one_row(
    client: httpx.AsyncClient, session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "B.md", "C.md", "D.md"], "Itaú": ["E.md"]})
    moved = tree["Itaú/E.md"]

    async def sorts() -> dict[uuid.UUID, tuple[uuid.UUID | None, str]]:
        rows = await session.execute(select(Node.id, Node.parent_id, Node.sort).where(Node.kb_id == tree.kb.id))
        return {id: (parent_id, sort) for id, parent_id, sort in rows}

    before = await sorts()
    response = await _move(client, moved.id, tree["Bradesco"].id, before_id=tree["Bradesco/C.md"].id)
    after = await sorts()

    assert response.json()["parent_id"] == str(tree["Bradesco"].id)
    assert {id for id in before if before[id] != after[id]} == {moved.id}
    assert await _titles(client, tree.kb.id, tree["Bradesco"].id) == ["A", "B", "E", "C", "D"]
    assert await _titles(client, tree.kb.id, tree["Itaú"].id) == []


async def test_move_into_own_descendant_is_422(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": {"Antigos": None}}, "Porto": ["Vistoria.md"]})

    for target in ["Bradesco", "Bradesco/Residencial", "Bradesco/Residencial/Antigos"]:
        response = await _move(client, tree["Bradesco"].id, tree[target].id)
        assert (response.status_code, response.json()["error"]) == (422, "validation")
    not_sibling = await _move(client, tree["Bradesco"].id, None, before_id=tree["Porto/Vistoria.md"].id)
    assert (not_sibling.status_code, not_sibling.json()["error"]) == (422, "validation")
    assert await _titles(client, tree.kb.id) == ["Bradesco", "Porto"]


async def test_sub_page_create_move_trash_restore(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Porto": ["Vistoria.md"], "CG 2026.pdf": None})
    page = tree["Bradesco/Renovação.md"].id
    sub_page = await _node(client, tree.kb.id, "Checklist", parent_id=page)
    await _node(client, tree.kb.id, "Itens", parent_id=sub_page)
    folder = await _move(client, tree["Porto"].id, page)
    file = await _move(client, tree["CG 2026.pdf"].id, page)

    assert (folder.status_code, file.status_code) == (200, 200)
    assert await _titles(client, tree.kb.id, page) == ["Checklist", "Porto", "CG 2026.pdf"]
    assert await _titles(client, tree.kb.id, sub_page) == ["Itens"]
    opened = (await client.get(f"/v1/nodes/{tree['Porto/Vistoria.md'].id}")).json()
    assert opened["path"] == "Bradesco/Renovação/Porto/Vistoria"

    await client.delete(f"/v1/nodes/{sub_page}")
    restored = (await client.post(f"/v1/nodes/{sub_page}/restore")).json()
    assert (restored["parent_id"], restored["to_root"]) == (str(page), False)

    await client.delete(f"/v1/nodes/{page}")
    gone = await client.get(f"/v1/kbs/{tree.kb.id}/children", params={"parent_id": str(page)})
    assert (gone.status_code, gone.json()["error"]) == (404, "not_found")
    assert await _titles(client, tree.kb.id) == ["Bradesco"]
    assert [item["title"] for item in (await client.get(f"/v1/kbs/{tree.kb.id}/trash")).json()] == ["Renovação"]

    restored = (await client.post(f"/v1/nodes/{page}/restore")).json()
    assert (restored["parent_id"], restored["to_root"]) == (str(tree["Bradesco"].id), False)
    assert await _titles(client, tree.kb.id, page) == ["Checklist", "Porto", "CG 2026.pdf"]
    assert await _titles(client, tree.kb.id, sub_page) == ["Itens"]
    assert await _titles(client, tree.kb.id, tree["Porto"].id) == ["Vistoria"]


async def test_move_page_into_its_own_sub_page_is_422(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Renovação.md": None, "CG 2026.pdf": None})
    page = tree["Renovação.md"].id
    sub_page = await _node(client, tree.kb.id, "Checklist", parent_id=page)
    deeper = await _node(client, tree.kb.id, "Itens", parent_id=sub_page)

    for target in [page, sub_page, deeper, tree["CG 2026.pdf"].id]:
        response = await _move(client, page, target)
        assert (response.status_code, response.json()["error"]) == (422, "validation")
    assert await _titles(client, tree.kb.id) == ["Renovação", "CG 2026.pdf"]
    assert await _titles(client, tree.kb.id, page) == ["Checklist"]


async def test_title_clash_is_409_title_taken(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md", "Sinistro.md"], "Renovação.md": None})
    bradesco = tree["Bradesco"].id

    created = await client.post(
        f"/v1/kbs/{tree.kb.id}/nodes", json={"kind": "page", "title": " renovação ", "parent_id": str(bradesco)}
    )
    renamed = await client.patch(f"/v1/nodes/{tree['Bradesco/Sinistro.md'].id}", json={"title": "RENOVAÇÃO"})
    moved = await _move(client, tree["Renovação.md"].id, bradesco)

    assert [(r.status_code, r.json()["error"], r.json()["details"]) for r in (created, renamed, moved)] == [
        (409, "title_taken", {"title": "renovação"}),
        (409, "title_taken", {"title": "RENOVAÇÃO"}),
        (409, "title_taken", {"title": "Renovação"}),
    ]
    assert await _titles(client, tree.kb.id, bradesco) == ["Renovação", "Sinistro"]
    same = await client.patch(f"/v1/nodes/{tree['Bradesco/Sinistro.md'].id}", json={"title": "  SINISTRO   anual "})
    assert same.json()["title"] == "SINISTRO anual"

    old = tree["Bradesco/Renovação.md"].id
    await client.delete(f"/v1/nodes/{old}")
    await _node(client, tree.kb.id, "Renovação", parent_id=bradesco)
    restored = await client.post(f"/v1/nodes/{old}/restore")
    assert (restored.status_code, restored.json()["error"]) == (409, "title_taken")
    assert [item["id"] for item in (await client.get(f"/v1/kbs/{tree.kb.id}/trash")).json()] == [str(old)]

    await _node(client, tree.kb.id, "Renovação", "folder", bradesco)
    assert await _titles(client, tree.kb.id, bradesco) == ["SINISTRO anual", "Renovação", "Renovação"]


async def test_trash_hides_the_subtree_from_children_and_search(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree(
        {
            "Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md", "CG 2026.pdf"]},
            "Itaú": ["Renovação.md"],
        }
    )
    residencial = tree["Bradesco/Residencial"]
    await client.delete(f"/v1/nodes/{tree['Bradesco/Residencial/Renovação.md'].id}")

    trashed = await client.delete(f"/v1/nodes/{residencial.id}")

    assert trashed.json()["deleted_at"] is not None
    assert await _titles(client, tree.kb.id, tree["Bradesco"].id) == []
    gone = await client.get(f"/v1/kbs/{tree.kb.id}/children", params={"parent_id": str(residencial.id)})
    assert (gone.status_code, gone.json()["error"]) == (404, "not_found")
    hits = (await client.get(f"/v1/kbs/{tree.kb.id}/search", params={"q": "renovacao"})).json()
    assert [(hit["id"], hit["path"]) for hit in hits] == [(str(tree["Itaú/Renovação.md"].id), "Itaú/Renovação")]
    assert (await client.get(f"/v1/kbs/{tree.kb.id}/search", params={"q": "apólice"})).json() == []
    items = (await client.get(f"/v1/kbs/{tree.kb.id}/trash")).json()
    assert {(item["title"], item["path"]) for item in items} == {
        ("Residencial", "Bradesco/Residencial"),
        ("Renovação", "Bradesco/Residencial/Renovação"),
    }

    restored = (await client.post(f"/v1/nodes/{residencial.id}/restore")).json()
    assert (restored["parent_id"], restored["to_root"]) == (str(tree["Bradesco"].id), False)
    assert await _titles(client, tree.kb.id, residencial.id) == ["Emissão de apólice", "CG 2026.pdf"]
    assert [item["title"] for item in (await client.get(f"/v1/kbs/{tree.kb.id}/trash")).json()] == ["Renovação"]
    hits = (await client.get(f"/v1/kbs/{tree.kb.id}/search", params={"q": "APOLICE"})).json()
    assert [hit["path"] for hit in hits] == ["Bradesco/Residencial/Emissão de apólice"]


async def test_restore_goes_to_root_when_the_parent_is_gone(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Itaú": None})
    page = tree["Bradesco/Renovação.md"]
    await client.delete(f"/v1/nodes/{page.id}")
    await client.delete(f"/v1/nodes/{tree['Bradesco'].id}")

    restored = (await client.post(f"/v1/nodes/{page.id}/restore")).json()

    assert (restored["parent_id"], restored["to_root"]) == (None, True)
    assert await _titles(client, tree.kb.id) == ["Itaú", "Renovação"]
    assert [item["title"] for item in (await client.get(f"/v1/kbs/{tree.kb.id}/trash")).json()] == ["Bradesco"]
    again = await client.post(f"/v1/nodes/{page.id}/restore")
    assert (again.status_code, again.json()["error"]) == (404, "not_found")
    inner = await client.post(f"/v1/nodes/{tree['Bradesco'].id}/restore")
    assert inner.status_code == 200


async def test_restore_re_keys_a_repeated_sort_key(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    folder = tree["Bradesco"].id
    first = await _node(client, tree.kb.id, "Renovação", parent_id=folder)
    await client.delete(f"/v1/nodes/{first}")
    # Placed last while "Renovação" is in the trash, so it gets the same key.
    await _node(client, tree.kb.id, "Sinistro", parent_id=folder)
    await _node(client, tree.kb.id, "Vistoria", parent_id=folder)

    restored = await client.post(f"/v1/nodes/{first}/restore")

    assert restored.status_code == 200
    children = await _children(client, tree.kb.id, folder)
    assert [node["title"] for node in children] == ["Sinistro", "Renovação", "Vistoria"]
    assert len({node["sort"] for node in children}) == 3


async def test_401_without_the_key(client: httpx.AsyncClient, session: AsyncSession, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})
    del client.headers["X-API-Key"]

    responses = [
        await client.get(f"/v1/kbs/{tree.kb.id}/children"),
        await client.post(f"/v1/kbs/{tree.kb.id}/nodes", json={"kind": "folder", "title": "Porto"}),
        await client.delete(f"/v1/nodes/{tree['Bradesco'].id}"),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [(401, "unauthorized")] * 3
    rows = await session.execute(select(Node.title, Node.deleted_at).where(Node.kb_id == tree.kb.id))
    assert list(rows) == [("Bradesco", None)]


async def test_open_a_file_and_a_folder_node(client: httpx.AsyncClient, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["CG 2026.pdf"]})
    file = tree["Bradesco/CG 2026.pdf"]
    await client.post(f"/v1/nodes/{file.id}/file", files={"file": ("CG 2026.pdf", b"%PDF-broken")})

    folder = (await client.get(f"/v1/nodes/{tree['Bradesco'].id}")).json()
    opened = (await client.get(f"/v1/nodes/{file.id}")).json()

    assert (folder["kind"], folder["path"], folder["page"], folder["file"], folder["versions"]) == (
        "folder",
        "Bradesco",
        None,
        None,
        0,
    )
    assert (opened["kind"], opened["path"], opened["page"], opened["versions"]) == (
        "file",
        "Bradesco/CG 2026.pdf",
        None,
        2,
    )
    assert (opened["file"]["mime"], opened["file"]["size"], opened["file"]["pages"]) == ("application/pdf", 11, None)
    assert set(opened["file"]) == {"size", "mime", "pages", "protected", "sha256"}


async def test_edit_description_locks_it_and_children_carry_counts(
    client: httpx.AsyncClient, session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["A.md", "B.md"]}, "Vazia": None})
    residencial = tree["Bradesco/Residencial"].id

    edited = await client.patch(f"/v1/nodes/{residencial}", json={"description": "  Produto residencial.  "})

    assert edited.status_code == 200
    row = await session.get(Node, residencial, populate_existing=True)
    assert row is not None and (row.description, row.description_locked, row.title) == (
        "Produto residencial.",
        True,
        "Residencial",
    )
    top = {node["title"]: node for node in await _children(client, tree.kb.id, None)}
    assert (top["Bradesco"]["child_count"], top["Vazia"]["child_count"]) == (1, 0)
    inside = await _children(client, tree.kb.id, tree["Bradesco"].id)
    assert (inside[0]["child_count"], inside[0]["has_children"], inside[0]["pages"], inside[0]["size"]) == (
        2,
        True,
        None,
        None,
    )
