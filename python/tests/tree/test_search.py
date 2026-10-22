from acervo.store.models import Node
from acervo.tree import search, trash


async def test_ignores_accents_and_case(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md"]}, "Arquivo": None})
    session.add_all(
        Node(kb_id=tree.kb.id, parent_id=tree["Arquivo"].id, kind="page", title=f"Item {i}", sort=f"a{i:04d}")
        for i in range(3000)
    )
    await session.flush()

    for query in ["emissao", "EMISSÃO", "Apolice"]:
        hits = await search.search(session, tree.kb.id, query)
        assert [hit.node.title for hit in hits] == ["Emissão de apólice"]


async def test_excludes_trashed_items(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"], "Itaú": ["Renovação.md"]})
    await trash.trash(session, tree["Bradesco"].id)

    hits = await search.search(session, tree.kb.id, "renovacao")

    assert [hit.node.id for hit in hits] == [tree["Itaú/Renovação.md"].id]


async def test_results_carry_their_path(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": {"Residencial": ["CG 2026.pdf", "Renovação.md"]}, "Renovação 2025.md": None})

    hits = await search.search(session, tree.kb.id, "renovação")

    assert [hit.path for hit in hits] == ["Bradesco/Residencial/Renovação", "Renovação 2025"]
