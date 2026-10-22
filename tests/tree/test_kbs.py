from acervo.tree import kbs, trash


async def test_create_rename_describe(session) -> None:
    kb = await kbs.create_kb(session, "  Seguros  ")

    await kbs.update_kb(session, kb.id, name="Seguros · Operação")
    await kbs.update_kb(session, kb.id, description="Apólices, sinistros e renovações")

    [summary] = await kbs.list_kbs(session)
    assert (summary.kb.name, summary.kb.description) == ("Seguros · Operação", "Apólices, sinistros e renovações")
    assert (summary.pages, summary.files) == (0, 0)


async def test_counts_ignore_trashed_items(session, make_tree) -> None:
    tree = await make_tree(
        {"Bradesco": ["Emissão de apólice.md", "CG 2026.pdf"], "Renovação.md": None, "Tabela.xlsx": None}
    )
    await trash.trash(session, tree["Bradesco"].id)

    [summary] = await kbs.list_kbs(session)
    assert (summary.pages, summary.files) == (1, 1)


async def test_trashed_base_leaves_the_list_and_comes_back(session, make_tree) -> None:
    tree = await make_tree({"Bradesco": ["Renovação.md"]})
    other = await kbs.create_kb(session, "Jurídico")

    await kbs.trash_kb(session, tree.kb.id)
    assert [summary.kb.id for summary in await kbs.list_kbs(session)] == [other.id]
    assert [kb.id for kb in await kbs.list_trashed_kbs(session)] == [tree.kb.id]

    await kbs.restore_kb(session, tree.kb.id)
    summaries = {summary.kb.id: summary for summary in await kbs.list_kbs(session)}
    assert summaries.keys() == {tree.kb.id, other.id}
    assert summaries[tree.kb.id].pages == 1
    assert await kbs.list_trashed_kbs(session) == []


async def test_name_filter(session, make_tree) -> None:
    await make_tree({}, name="Seguros · Operação")
    juridico = await kbs.create_kb(session, "Jurídico")

    assert [summary.kb.id for summary in await kbs.list_kbs(session, "JURIDICO")] == [juridico.id]
    assert [summary.kb.name for summary in await kbs.list_kbs(session, "seguros")] == ["Seguros · Operação"]
