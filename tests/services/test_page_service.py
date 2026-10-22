import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.errors import StalePage
from acervo.core.settings import Settings
from acervo.db.models import Kb, Node, PageDraft, PageLink, PageVersion
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.kb import KbCreate
from acervo.schemas.node import NodeAdd
from acervo.schemas.page import DraftPut, PageSave, PageVersionSummary
from acervo.services.page_service import PageService
from acervo.services.tree_service import TreeService

MakeTree = Callable[..., Awaitable[Any]]

PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TREE = {
    "Bradesco": {"Residencial": ["Emissão de apólice.md", "Renovação.md", "Sinistro.md"], "Auto": ["Sinistro.md"]},
    "Porto": ["Sinistro.md", "Vistoria.md"],
}


@dataclass
class Services:
    pages: PageService
    tree: TreeService


@pytest.fixture
async def services(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[Services]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield Services(PageService(uow), TreeService(uow))


async def _write(pages: PageService, node_id: UUID, markdown: str) -> PageVersionSummary:
    base = (await pages.read(node_id)).version_id
    return await pages.save(node_id, PageSave(markdown=markdown, base_version_id=base))


async def _markdown(pages: PageService, node_id: UUID) -> str:
    return (await pages.read(node_id)).markdown


async def test_create_writes_an_empty_version_1(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})

    node = await services.tree.create(tree.kb.id, NodeAdd(parent_id=tree["Bradesco"].id, kind="page", title="Prazos"))

    page = await services.pages.read(node.id)
    assert (page.markdown, page.draft, page.links, page.sections) == ("", None, {}, [])
    assert [(v.id, v.author) for v in await services.pages.versions(node.id)] == [(page.version_id, "user")]


async def test_save_creates_a_whole_file_version_by_user(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = (await services.pages.read(page.id)).version_id

    saved = await _write(services.pages, page.id, "# Emissão de apólice\n\n## Documentos\n- RG\n")

    assert saved.id != first
    assert saved.author == "user"
    current = await services.pages.read(page.id)
    assert (current.version_id, current.markdown) == (saved.id, "# Emissão de apólice\n\n## Documentos\n- RG\n")
    assert [(s.anchor, s.heading) for s in current.sections] == [("documentos", "Documentos")]


async def test_unchanged_text_creates_no_version(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await services.pages.read(page.id)

    assert (await _write(services.pages, page.id, first.markdown)).id == first.version_id
    assert len(await services.pages.versions(page.id)) == 1


async def test_stale_base_raises_with_diff_and_keeps_the_draft(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    base = (await services.pages.read(page.id)).version_id
    theirs = await _write(services.pages, page.id, "# Emissão de apólice\nNova linha\n")
    await services.pages.put_draft(page.id, DraftPut(markdown="Minha linha\n", base_version_id=base))

    with pytest.raises(StalePage) as raised:
        await services.pages.save(page.id, PageSave(markdown="Minha linha\n", base_version_id=base))

    assert raised.value.details == {
        "current_version_id": str(theirs.id),
        "markdown": "# Emissão de apólice\nNova linha\n",
        "diff": [{"op": "same", "text": "# Emissão de apólice"}, {"op": "add", "text": "Nova linha"}],
    }
    assert len(await services.pages.versions(page.id)) == 2
    draft = (await services.pages.read(page.id)).draft
    assert draft is not None and (draft.markdown, draft.base_version_id) == ("Minha linha\n", base)


async def test_force_saves_on_top_and_keeps_both(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    base = (await services.pages.read(page.id)).version_id
    theirs = await _write(services.pages, page.id, "# Emissão de apólice\nNova linha\n")

    mine = await services.pages.save(
        page.id, PageSave(markdown="# Emissão de apólice\nMinha linha\n", base_version_id=base, force=True)
    )

    assert [v.id for v in await services.pages.versions(page.id)] == [mine.id, theirs.id, base]


async def test_restore_writes_a_new_version(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await services.pages.read(page.id)
    second = await _write(services.pages, page.id, "# Emissão de apólice\nSegunda\n")

    restored = await services.pages.restore(page.id, first.version_id)

    assert restored.version_id not in (first.version_id, second.id)
    assert restored.markdown == first.markdown
    history = [v.id for v in await services.pages.versions(page.id)]
    assert history == [restored.version_id, second.id, first.version_id]
    diff = await services.pages.diff(page.id, second.id)
    assert [(line.op, line.text) for line in diff.lines] == [
        ("same", "# Emissão de apólice"),
        ("add", "Segunda"),
    ]


async def test_save_drops_the_draft(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = (await services.pages.read(page.id)).version_id
    draft = DraftPut(markdown="# Emissão de apólice\nRascunho\n", base_version_id=first)
    await services.pages.put_draft(page.id, draft)

    await _write(services.pages, page.id, "# Emissão de apólice\nRascunho\n")

    assert (await services.pages.read(page.id)).draft is None


async def test_draft_is_replaced_discarded_and_never_a_version(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(["Renovação.md"]))["Renovação.md"]
    base = (await services.pages.read(page.id)).version_id

    await services.pages.put_draft(page.id, DraftPut(markdown="primeiro", base_version_id=base))
    await services.pages.put_draft(page.id, DraftPut(markdown="segundo", base_version_id=base))

    current = await services.pages.read(page.id)
    assert current.draft is not None and (current.draft.markdown, current.draft.base_version_id) == ("segundo", base)
    assert (current.markdown, [v.id for v in await services.pages.versions(page.id)]) == ("# Renovação\n", [base])
    await services.pages.discard_draft(page.id)
    assert (await services.pages.read(page.id)).draft is None


async def test_history_newest_first_without_text(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = (await services.pages.read(page.id)).version_id
    second = await _write(services.pages, page.id, "dois\n")
    third = await _write(services.pages, page.id, "três\n")

    history = await services.pages.versions(page.id)

    assert [v.id for v in history] == [third.id, second.id, first]
    assert history[0].created_at > history[1].created_at > history[2].created_at
    assert {v.author for v in history} == {"user"}
    assert not hasattr(history[0], "markdown")


async def test_links_resolve_missing_and_ambiguous(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]
    await _write(services.pages, page.id, "Veja [[Renovação]], [[ bradesco ]], [[Cancelamento]] e [[Sinistro]].\n")
    tree["Porto/Sinistro.md"].deleted_at = datetime.now(UTC)
    await session.flush()

    assert (await services.pages.read(page.id)).links == {
        "renovação": tree["Bradesco/Residencial/Renovação.md"].id,
        "bradesco": "missing",
        "cancelamento": "missing",
        "sinistro": "ambiguous",
    }


async def test_ambiguous_prefers_same_folder(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree(TREE)
    page = tree["Bradesco/Residencial/Emissão de apólice.md"]
    await _write(services.pages, page.id, "Veja [[Sinistro]].\n")

    assert (await services.pages.read(page.id)).links == {"sinistro": tree["Bradesco/Residencial/Sinistro.md"].id}


async def test_titles_with_repeated_spaces_resolve(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]
    created = await services.tree.create(
        tree.kb.id, NodeAdd(parent_id=tree["Porto"].id, kind="page", title="Tabela  de   prazos")
    )
    renamed = await services.tree.rename(tree["Porto/Sinistro.md"].id, "Aviso  de sinistro")
    await _write(services.pages, page.id, "Ver [[Tabela  de   prazos]] e [[Aviso de  sinistro]].\n")

    assert (created.title, renamed.title) == ("Tabela de prazos", "Aviso de sinistro")
    assert (await services.pages.read(page.id)).links == {
        "tabela de prazos": created.id,
        "aviso de sinistro": renamed.id,
    }


async def test_rename_fixes_linking_pages_as_new_versions(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree(TREE)
    emission, vistoria = tree["Bradesco/Residencial/Emissão de apólice.md"], tree["Porto/Vistoria.md"]
    await _write(services.pages, emission.id, "Antes da [[Renovação]], ver [[renovação]].\n")
    await _write(services.pages, vistoria.id, "Depois da [[Renovação]].\n")
    unrelated = tree["Porto/Sinistro.md"].id
    unrelated_version = await _write(services.pages, unrelated, "Renovação não é link aqui.\n")

    await services.tree.rename(tree["Bradesco/Residencial/Renovação.md"].id, "Renovação anual")

    assert await _markdown(services.pages, emission.id) == "Antes da [[Renovação anual]], ver [[Renovação anual]].\n"
    assert await _markdown(services.pages, vistoria.id) == "Depois da [[Renovação anual]].\n"
    assert [v.author for v in await services.pages.versions(emission.id)] == ["user"] * 3
    assert (await services.pages.read(unrelated)).version_id == unrelated_version.id


async def test_rename_fixes_only_links_to_that_page(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree(
        {
            "Bradesco": {"Residencial": ["Renovação.md", "Emissão de apólice.md"], "Auto": ["Sinistro.md"]},
            "Porto": ["Renovação.md", "Vistoria.md"],
        }
    )
    emission = tree["Bradesco/Residencial/Emissão de apólice.md"].id
    other, ambiguous = tree["Porto/Vistoria.md"].id, tree["Bradesco/Auto/Sinistro.md"].id
    await _write(services.pages, emission, "Ver [[Renovação]].\n")
    other_version = await _write(services.pages, other, "Ver [[Renovação]].\n")
    ambiguous_version = await _write(services.pages, ambiguous, "Ver [[Renovação]].\n")

    await services.tree.rename(tree["Bradesco/Residencial/Renovação.md"].id, "Renovação anual")

    assert await _markdown(services.pages, emission) == "Ver [[Renovação anual]].\n"
    assert (await services.pages.read(other)).version_id == other_version.id
    assert (await services.pages.read(ambiguous)).version_id == ambiguous_version.id


async def test_link_table_follows_the_latest_version(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    page = (await make_tree(TREE))["Porto/Vistoria.md"]

    async def rows() -> set[str]:
        return set(await session.scalars(select(PageLink.target).where(PageLink.from_node_id == page.id)))

    await _write(services.pages, page.id, "[[Sinistro]] e [[Renovação]]\n")
    assert await rows() == {"sinistro", "renovação"}

    await _write(services.pages, page.id, "Só [[Emissão de apólice]]\n")
    assert await rows() == {"emissão de apólice"}


@pytest.fixture
async def committed_page(test_settings: Settings) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], UUID]]:
    """A page written by sessions on connections of their own that commit, as parallel requests do; removed after."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with UnitOfWork(sessions) as uow:
        kb = await uow.kbs.create(KbCreate(name="Edições em paralelo"))
        await uow.commit()
        page = await TreeService(uow).create(kb.id, NodeAdd(kind="page", title="Prazos"))
    yield sessions, page.id
    async with sessions() as session:
        of_base = select(Node.id).where(Node.kb_id == kb.id)
        await session.execute(delete(PageLink).where(PageLink.from_node_id.in_(of_base)))
        await session.execute(delete(PageDraft).where(PageDraft.node_id.in_(of_base)))
        await session.execute(delete(PageVersion).where(PageVersion.node_id.in_(of_base)))
        await session.execute(delete(Node).where(Node.kb_id == kb.id))
        await session.execute(delete(Kb).where(Kb.id == kb.id))
        await session.commit()
    await engine.dispose()


async def _save_committed(
    sessions: async_sessionmaker[AsyncSession], node_id: UUID, base: UUID, markdown: str
) -> PageVersionSummary:
    async with UnitOfWork(sessions) as uow:
        return await PageService(uow).save(node_id, PageSave(markdown=markdown, base_version_id=base))


async def test_concurrent_saves_from_one_version_give_one_stale_page(
    committed_page: tuple[async_sessionmaker[AsyncSession], UUID],
) -> None:
    sessions, node_id = committed_page
    async with UnitOfWork(sessions) as uow:
        base = (await PageService(uow).read(node_id)).version_id

    results = await asyncio.gather(
        *(_save_committed(sessions, node_id, base, f"# Prazos\n{name}\n") for name in ("Ana", "Bruno")),
        return_exceptions=True,
    )

    assert sorted(isinstance(result, StalePage) for result in results) == [False, True]
    async with UnitOfWork(sessions) as uow:
        assert len(await PageService(uow).versions(node_id)) == 2
