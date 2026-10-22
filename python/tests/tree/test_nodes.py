import uuid

import pytest
from sqlalchemy import select

from acervo.errors import ConflictError, ValidationError
from acervo.store.models import Node
from acervo.store.repositories import path
from acervo.tree import nodes


async def test_children_follow_the_order_the_person_set(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "B.md", "C.md"], "Arquivo": None})
    session.add_all(
        Node(kb_id=tree.kb.id, parent_id=tree["Arquivo"].id, kind="page", title=f"Item {i}", sort=f"a{i:04d}")
        for i in range(3000)
    )
    await session.flush()
    bradesco = tree["Bradesco"].id

    await nodes.move(session, tree["Bradesco/C.md"].id, bradesco, before_id=tree["Bradesco/A.md"].id)
    await nodes.move(session, tree["Bradesco/A.md"].id, bradesco)
    new = await nodes.create(session, tree.kb.id, bradesco, "page", "D")
    await nodes.move(session, new.id, bradesco, before_id=tree["Bradesco/B.md"].id)

    titles = [node.title for node in await nodes.children(session, tree.kb.id, bradesco)]
    assert titles == ["C", "D", "B", "A"]


async def test_move_between_siblings_changes_only_the_moved_row(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "B.md", "C.md", "D.md"], "Itaú": ["E.md"]})
    moved = tree["Itaú/E.md"]

    async def sorts() -> dict[uuid.UUID, tuple[uuid.UUID | None, str]]:
        rows = await session.execute(select(Node.id, Node.parent_id, Node.sort).where(Node.kb_id == tree.kb.id))
        return {id: (parent_id, sort) for id, parent_id, sort in rows}

    before = await sorts()
    await nodes.move(session, moved.id, tree["Bradesco"].id, before_id=tree["Bradesco/C.md"].id)
    after = await sorts()

    assert {id for id in before if before[id] != after[id]} == {moved.id}
    titles = [node.title for node in await nodes.children(session, tree.kb.id, tree["Bradesco"].id)]
    assert titles == ["A", "B", "E", "C", "D"]
    assert await path(session, moved.id) == "Bradesco/E"


async def test_move_into_own_descendant_is_refused(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": {"Antigos": None}}})
    bradesco = tree["Bradesco"]

    for target in ["Bradesco", "Bradesco/Residencial", "Bradesco/Residencial/Antigos"]:
        with pytest.raises(ValidationError):
            await nodes.move(session, bradesco.id, tree[target].id)
    assert (await nodes.live_node(session, bradesco.id)).parent_id is None


async def test_sibling_title_clash_is_refused(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md", "Sinistro.md"], "Renovação.md": None})
    bradesco = tree["Bradesco"].id

    with pytest.raises(ConflictError, match="já existe"):
        await nodes.create(session, tree.kb.id, bradesco, "page", "renovação")
    with pytest.raises(ConflictError, match="já existe"):
        await nodes.rename(session, tree["Bradesco/Sinistro.md"].id, "RENOVAÇÃO")
    with pytest.raises(ConflictError, match="já existe"):
        await nodes.move(session, tree["Renovação.md"].id, bradesco)

    titles = [node.title for node in await nodes.children(session, tree.kb.id, bradesco)]
    assert titles == ["Renovação", "Sinistro"]
    assert (await nodes.rename(session, tree["Bradesco/Sinistro.md"].id, "SINISTRO")).title == "SINISTRO"


async def test_page_and_folder_may_share_a_title(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"]})

    folder = await nodes.create(session, tree.kb.id, tree["Bradesco"].id, "folder", "Renovação")

    kinds = [(node.kind, node.title) for node in await nodes.children(session, tree.kb.id, tree["Bradesco"].id)]
    assert kinds == [("page", "Renovação"), ("folder", "Renovação")]
    assert await path(session, folder.id) == "Bradesco/Renovação"
