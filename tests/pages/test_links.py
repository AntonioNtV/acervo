from datetime import UTC, datetime

from sqlalchemy import select

from acervo.pages import links, versions
from acervo.store.models import PageLink
from acervo.tree import nodes

TREE = {
    "Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md", "Sinistro.md"], "Auto": ["Sinistro.md"]},
    "Porto": ["Sinistro.md", "Vistoria.md"],
}


async def _write(session, page, markdown: str):
    return await versions.save(session, page, markdown, (await versions.current(session, page.id)).id)


async def test_links_resolve_missing_and_ambiguous(session, make_tree) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]
    await _write(session, page, "Veja [[Renovação]], [[ bradesco ]], [[Cancelamento]] e [[Sinistro]].\n")
    tree["Porto/Sinistro.md"].deleted_at = datetime.now(UTC)
    await session.flush()

    assert await links.resolve(session, page) == {
        "renovação": tree["Bradesco/Residencial/Renovação.md"].id,
        "bradesco": "missing",
        "cancelamento": "missing",
        "sinistro": "ambiguous",
    }


async def test_ambiguous_prefers_same_folder(session, make_tree) -> None:
    tree = await make_tree(TREE)
    page = tree["Bradesco/Residencial/Emissão de apólice.md"]
    await _write(session, page, "Veja [[Sinistro]].\n")

    assert await links.resolve(session, page) == {"sinistro": tree["Bradesco/Residencial/Sinistro.md"].id}


async def test_titles_with_repeated_spaces_resolve(session, make_tree) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]
    created = await nodes.create(session, tree.kb.id, tree["Porto"].id, "page", "Tabela  de   prazos")
    renamed = await nodes.rename(session, tree["Porto/Sinistro.md"].id, "Aviso  de sinistro")
    await _write(session, page, "Ver [[Tabela  de   prazos]] e [[Aviso de  sinistro]].\n")

    assert (created.title, renamed.title) == ("Tabela de prazos", "Aviso de sinistro")
    assert await links.resolve(session, page) == {"tabela de prazos": created.id, "aviso de sinistro": renamed.id}


async def test_rename_fixes_linking_pages_as_new_versions(session, make_tree) -> None:
    tree = await make_tree(TREE)
    emission, vistoria = tree["Bradesco/Residencial/Emissão de apólice.md"], tree["Porto/Vistoria.md"]
    await _write(session, emission, "Antes da [[Renovação]], ver [[renovação]].\n")
    await _write(session, vistoria, "Depois da [[Renovação]].\n")
    unrelated = await _write(session, tree["Porto/Sinistro.md"], "Renovação não é link aqui.\n")

    fixed = await links.fix_links(session, tree["Bradesco/Residencial/Renovação.md"], "Renovação anual")

    assert {v.node_id for v in fixed} == {emission.id, vistoria.id}
    assert {v.author for v in fixed} == {"user"}
    assert (await versions.current(session, emission.id)).markdown == (
        "Antes da [[Renovação anual]], ver [[Renovação anual]].\n"
    )
    assert (await versions.current(session, vistoria.id)).markdown == "Depois da [[Renovação anual]].\n"
    assert len(await versions.history(session, emission.id)) == 3
    assert (await versions.current(session, unrelated.node_id)).id == unrelated.id


async def test_rename_fixes_only_links_to_that_page(session, make_tree) -> None:
    tree = await make_tree(
        {
            "Bradesco": {"Residencial": ["Renovação.md", "Emissão de apólice.md"], "Auto": ["Sinistro.md"]},
            "Porto": ["Renovação.md", "Vistoria.md"],
        }
    )
    renewal = tree["Bradesco/Residencial/Renovação.md"]
    emission = await _write(session, tree["Bradesco/Residencial/Emissão de apólice.md"], "Ver [[Renovação]].\n")
    other = await _write(session, tree["Porto/Vistoria.md"], "Ver [[Renovação]].\n")
    ambiguous = await _write(session, tree["Bradesco/Auto/Sinistro.md"], "Ver [[Renovação]].\n")

    fixed = await links.fix_links(session, renewal, "Renovação anual")

    assert [v.node_id for v in fixed] == [emission.node_id]
    assert (await versions.current(session, emission.node_id)).markdown == "Ver [[Renovação anual]].\n"
    assert (await versions.current(session, other.node_id)).id == other.id
    assert (await versions.current(session, ambiguous.node_id)).id == ambiguous.id


async def test_link_table_follows_the_latest_version(session, make_tree) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]

    async def rows() -> set[str]:
        return set(await session.scalars(select(PageLink.target).where(PageLink.from_node_id == page.id)))

    await _write(session, page, "[[Sinistro]] e [[Renovação]]\n")
    assert await rows() == {"sinistro", "renovação"}

    await _write(session, page, "Só [[Emissão de apólice]]\n")
    assert await rows() == {"emissão de apólice"}
