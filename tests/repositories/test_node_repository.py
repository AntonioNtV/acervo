import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import NotFoundError, ValidationError
from acervo.db.models import Node
from acervo.repositories.kb import KbRepository
from acervo.repositories.node import SEARCH_LIMIT, NodeRepository
from acervo.schemas.kb import KbUpdate

MakeTree = Callable[..., Awaitable[Any]]


@pytest.fixture
def nodes(session: AsyncSession) -> NodeRepository:
    return NodeRepository(session)


async def test_path_joins_titles_from_the_root(nodes: NodeRepository, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}})

    assert await nodes.path(tree["Bradesco/Residencial/Emissão de apólice.md"].id) == (
        "Bradesco/Residencial/Emissão de apólice"
    )
    assert await nodes.paths([tree["Bradesco"].id, tree["Bradesco/Residencial/CG 2026.pdf"].id]) == {
        tree["Bradesco"].id: "Bradesco",
        tree["Bradesco/Residencial/CG 2026.pdf"].id: "Bradesco/Residencial/CG 2026.pdf",
    }
    with pytest.raises(NotFoundError):
        await nodes.path(uuid.uuid4())


async def test_a_page_is_a_valid_parent(nodes: NodeRepository, session: AsyncSession, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md", "CG 2026.pdf"], "Itaú": ["Sinistro.md"]})
    other = await make_tree({"Porto": ["Vistoria.md"]}, name="Jurídico")

    await nodes.live_parent(tree.kb.id, None)
    await nodes.live_parent(tree.kb.id, tree["Bradesco"].id)
    await nodes.live_parent(tree.kb.id, tree["Bradesco/Renovação.md"].id)
    with pytest.raises(ValidationError):
        await nodes.live_parent(tree.kb.id, tree["Bradesco/CG 2026.pdf"].id)
    for foreign in (other["Porto"], other["Porto/Vistoria.md"]):
        with pytest.raises(ValidationError):
            await nodes.live_parent(tree.kb.id, foreign.id)
    await nodes.trash_subtree(tree["Itaú"].id)
    for trashed in (tree["Itaú"], tree["Itaú/Sinistro.md"]):
        with pytest.raises(NotFoundError):
            await nodes.live_parent(tree.kb.id, trashed.id)
    await KbRepository(session).update(other.kb.id, KbUpdate(deleted_at=tree.kb.created_at))
    with pytest.raises(NotFoundError):
        await nodes.live_parent(other.kb.id, None)


async def test_last_sort_ignores_trashed_and_other_folders(nodes: NodeRepository, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "B.md", "C.md"], "Itaú": None})
    bradesco = tree["Bradesco"].id
    await nodes.trash_subtree(tree["Bradesco/C.md"].id)

    assert await nodes.last_sort(tree.kb.id, bradesco) == tree["Bradesco/B.md"].sort
    assert await nodes.last_sort(tree.kb.id, bradesco, below=tree["Bradesco/B.md"].sort) == tree["Bradesco/A.md"].sort
    assert await nodes.last_sort(tree.kb.id, bradesco, excluding=tree["Bradesco/B.md"].id) == (
        tree["Bradesco/A.md"].sort
    )
    assert await nodes.last_sort(tree.kb.id, tree["Itaú"].id) is None


async def test_title_taken_by_a_live_sibling_of_the_same_kind(
    nodes: NodeRepository, session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md", "Sinistro.md"], "Itaú": None})
    bradesco = tree["Bradesco"].id

    assert await nodes.title_taken(tree.kb.id, bradesco, "page", "RENOVAÇÃO")
    assert not await nodes.title_taken(tree.kb.id, bradesco, "folder", "Renovação")
    assert not await nodes.title_taken(tree.kb.id, None, "page", "Renovação")
    assert await nodes.title_taken(tree.kb.id, None, "folder", "itaú")
    await nodes.trash_subtree(tree["Bradesco/Sinistro.md"].id)
    assert not await nodes.title_taken(tree.kb.id, bradesco, "page", "Sinistro")


async def test_search_ignores_accents_and_case(
    nodes: NodeRepository, session: AsyncSession, make_tree: MakeTree
) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md"]}, "Arquivo": None})
    session.add_all(
        Node(kb_id=tree.kb.id, parent_id=tree["Arquivo"].id, kind="page", title=f"Item {i}", sort=f"a{i:04d}")
        for i in range(3000)
    )
    await session.flush()

    for query in ["emissao", "EMISSÃO", "Apolice"]:
        assert [node.title for node in await nodes.search(tree.kb.id, query)] == ["Emissão de apólice"]
    assert [node.title for node in await nodes.search(tree.kb.id, "100%")] == []
    assert len(await nodes.search(tree.kb.id, "item")) == SEARCH_LIMIT
