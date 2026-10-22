import pytest

from acervo.errors import ConflictError
from acervo.tree import nodes, search, trash


async def test_trashing_a_folder_hides_its_subtree(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}, "Itaú": None})
    residencial = tree["Bradesco/Residencial"]

    await trash.trash(session, residencial.id)

    assert await nodes.children(session, tree.kb.id, tree["Bradesco"].id) == []
    assert await search.search(session, tree.kb.id, "apólice") == []
    items = await trash.list_trash(session, tree.kb.id)
    assert [(item.node.id, item.path) for item in items] == [(residencial.id, "Bradesco/Residencial")]


async def test_restore_brings_the_subtree_back(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md", "CG 2026.pdf"]}})
    residencial = tree["Bradesco/Residencial"]
    await trash.trash(session, tree["Bradesco/Residencial/Renovação.md"].id)
    await trash.trash(session, residencial.id)

    restored = await trash.restore(session, residencial.id)

    assert (restored.node.parent_id, restored.to_root) == (tree["Bradesco"].id, False)
    titles = [node.title for node in await nodes.children(session, tree.kb.id, residencial.id)]
    assert titles == ["Emissão de apólice", "CG 2026.pdf"]
    assert [item.node.title for item in await trash.list_trash(session, tree.kb.id)] == ["Renovação"]


async def test_restore_goes_to_root_when_parent_is_gone(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Itaú": None})
    page = tree["Bradesco/Renovação.md"]
    await trash.trash(session, page.id)
    await trash.trash(session, tree["Bradesco"].id)

    restored = await trash.restore(session, page.id)

    assert (restored.node.parent_id, restored.to_root) == (None, True)
    titles = [node.title for node in await nodes.children(session, tree.kb.id, None)]
    assert titles == ["Itaú", "Renovação"]
    assert [item.node.title for item in await trash.list_trash(session, tree.kb.id)] == ["Bradesco"]


async def test_restore_with_a_title_clash_is_refused(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"]})
    page = tree["Bradesco/Renovação.md"]
    await trash.trash(session, page.id)
    await nodes.create(session, tree.kb.id, tree["Bradesco"].id, "page", "Renovação")

    with pytest.raises(ConflictError, match="já existe"):
        await trash.restore(session, page.id)
    assert [item.node.id for item in await trash.list_trash(session, tree.kb.id)] == [page.id]
