import pytest

from acervo.errors import ConflictError
from acervo.pages import drafts, versions

PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}}


async def test_save_creates_a_whole_file_version_by_user(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await versions.current(session, page.id)

    saved = await versions.save(session, page, "# Emissão de apólice\n\n## Documentos\n- RG\n", first.id)

    assert saved.id != first.id
    assert (saved.markdown, saved.author) == ("# Emissão de apólice\n\n## Documentos\n- RG\n", "user")
    assert (await versions.current(session, page.id)).id == saved.id


async def test_unchanged_text_creates_no_version(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await versions.current(session, page.id)

    assert (await versions.save(session, page, first.markdown, first.id)).id == first.id
    assert len(await versions.history(session, page.id)) == 1


async def test_stale_base_raises_conflict_with_diff(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    base = await versions.current(session, page.id)
    theirs = await versions.save(session, page, "# Emissão de apólice\nNova linha\n", base.id)

    with pytest.raises(ConflictError) as raised:
        await versions.save(session, page, "# Emissão de apólice\nMinha linha\n", base.id)

    assert raised.value.detail == {
        "current_version_id": str(theirs.id),
        "markdown": theirs.markdown,
        "diff": [{"op": "same", "text": "# Emissão de apólice"}, {"op": "add", "text": "Nova linha"}],
    }
    assert len(await versions.history(session, page.id)) == 2


async def test_force_saves_on_top_and_keeps_both(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    base = await versions.current(session, page.id)
    theirs = await versions.save(session, page, "# Emissão de apólice\nNova linha\n", base.id)

    mine = await versions.save(session, page, "# Emissão de apólice\nMinha linha\n", base.id, force=True)

    assert [v.id for v in await versions.history(session, page.id)] == [mine.id, theirs.id, base.id]


async def test_restore_writes_a_new_version(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await versions.current(session, page.id)
    second = await versions.save(session, page, "# Emissão de apólice\nSegunda\n", first.id)

    restored = await versions.restore(session, first.id)

    assert restored.id not in (first.id, second.id)
    assert restored.markdown == first.markdown
    assert [v.id for v in await versions.history(session, page.id)] == [restored.id, second.id, first.id]


async def test_save_discards_the_draft(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await versions.current(session, page.id)
    await drafts.put(session, page.id, "# Emissão de apólice\nRascunho\n", first.id)

    await versions.save(session, page, "# Emissão de apólice\nRascunho\n", first.id)

    assert await drafts.get(session, page.id) is None


async def test_history_newest_first(session, make_tree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await versions.current(session, page.id)
    second = await versions.save(session, page, "dois\n", first.id)
    third = await versions.save(session, page, "três\n", second.id)

    history = await versions.history(session, page.id)

    assert [v.markdown for v in history] == ["três\n", "dois\n", first.markdown]
    assert [v.id for v in history] == [third.id, second.id, first.id]
    assert history[0].created_at > history[1].created_at > history[2].created_at
    assert {v.author for v in history} == {"user"}
