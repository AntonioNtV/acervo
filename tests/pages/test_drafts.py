from acervo.pages import drafts, versions


async def test_put_get_discard(session, make_tree) -> None:
    page = (await make_tree(["Renovação.md"]))["Renovação.md"]
    base = await versions.current(session, page.id)

    await drafts.put(session, page.id, "primeiro", base.id)
    await drafts.put(session, page.id, "segundo", base.id)
    draft = await drafts.get(session, page.id)
    assert (draft.markdown, draft.base_version_id) == ("segundo", base.id)

    await drafts.discard(session, page.id)
    assert await drafts.get(session, page.id) is None


async def test_draft_is_not_a_version(session, make_tree) -> None:
    page = (await make_tree(["Renovação.md"]))["Renovação.md"]
    base = await versions.current(session, page.id)

    await drafts.put(session, page.id, "# Renovação\nRascunho\n", base.id)

    assert [v.id for v in await versions.history(session, page.id)] == [base.id]
    assert (await versions.current(session, page.id)).markdown == "# Renovação\n"
