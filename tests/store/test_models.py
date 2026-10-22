import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from acervo.store.models import File, Node, PageVersion
from acervo.store.repositories import sibling_title_taken


def _page(tree, parent: Node | None, title: str) -> Node:
    return Node(
        id=uuid.uuid4(),
        kb_id=tree.kb.id,
        parent_id=parent.id if parent else None,
        kind="page",
        title=title,
        sort="b0",
    )


@pytest.mark.parametrize("folder", [None, "Bradesco"])
async def test_live_siblings_cannot_share_a_title(session, make_tree, folder) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Renovação.md": None})
    parent = tree[folder] if folder else None

    assert await sibling_title_taken(session, tree.kb.id, parent.id if parent else None, "page", "RENOVAÇÃO")
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(_page(tree, parent, "renovação"))


async def test_a_trashed_sibling_frees_its_title(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"]})
    tree["Bradesco/Renovação.md"].deleted_at = datetime.now(UTC)
    await session.flush()

    assert not await sibling_title_taken(session, tree.kb.id, tree["Bradesco"].id, "page", "Renovação")
    session.add(_page(tree, tree["Bradesco"], "Renovação"))
    await session.flush()


async def test_make_tree_builds_folders_pages_and_files(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2026.pdf"]}})

    folder = tree["Bradesco/Residencial"]
    page = tree["Bradesco/Residencial/Emissão de apólice.md"]
    pdf = tree["Bradesco/Residencial/CG 2026.pdf"]
    assert (tree["Bradesco"].kind, tree["Bradesco"].parent_id) == ("folder", None)
    assert (folder.kind, folder.parent_id) == ("folder", tree["Bradesco"].id)
    assert (page.kind, page.title, page.parent_id) == ("page", "Emissão de apólice", folder.id)
    assert (pdf.kind, pdf.title, pdf.parent_id) == ("file", "CG 2026.pdf", folder.id)

    versions = await session.scalar(select(func.count()).where(PageVersion.node_id == page.id))
    assert versions == 1
    file = await session.scalar(select(File).where(File.node_id == pdf.id))
    assert file.mime == "application/pdf"
    assert file.storage_key == f"kb/{tree.kb.id}/{file.sha256}"
