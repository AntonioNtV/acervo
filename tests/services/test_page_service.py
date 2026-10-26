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
from acervo.db.models import Account, Kb, Node, Organization, PageDraft, PageLink, PageVersion
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountCreate
from acervo.schemas.kb import KbCreate
from acervo.schemas.node import NodeAdd
from acervo.schemas.page import PageTextPut, PageTextSaved, PageVersionSummary
from acervo.services.page_service import PageService
from acervo.services.tree_service import TreeService

MakeTree = Callable[..., Awaitable[Any]]
IDLE = 300

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
async def services(uow: UnitOfWork, session: AsyncSession, default_account_id: UUID) -> AsyncIterator[Services]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        uow.act_as(default_account_id)
        yield Services(PageService(uow), TreeService(uow))


async def _type(pages: PageService, node_id: UUID, markdown: str, idle: int = IDLE) -> PageTextSaved:
    revision = (await pages.read(node_id)).revision
    return await pages.put_text(node_id, PageTextPut(markdown=markdown, revision=revision), idle)


async def _write(pages: PageService, node_id: UUID, markdown: str) -> PageVersionSummary:
    """Types `markdown` and leaves the page: its newest version."""
    await _type(pages, node_id, markdown)
    await pages.cut(node_id)
    return (await pages.versions(node_id))[0]


async def _stored(session: AsyncSession, node_id: UUID) -> list[tuple[str, bool]]:
    """Every version's text, oldest first, and whether it carries an editing span; without cutting first."""
    query = select(PageVersion).where(PageVersion.node_id == node_id).order_by(PageVersion.created_at)
    return [
        (v.markdown, v.edit_started_at is not None and v.edit_ended_at is not None)
        for v in await session.scalars(query.execution_options(populate_existing=True))
    ]


async def _markdown(pages: PageService, node_id: UUID) -> str:
    return (await pages.read(node_id)).markdown


async def test_create_writes_an_empty_version_1(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": None})

    node = await services.tree.create(tree.kb.id, NodeAdd(parent_id=tree["Bradesco"].id, kind="page", title="Prazos"))

    page = await services.pages.read(node.id)
    assert (page.markdown, page.revision, page.links, page.sections) == ("", 0, {}, [])
    assert [v.id for v in await services.pages.versions(node.id)] == [page.version_id]


async def test_save_creates_a_whole_file_version_by_user(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = (await services.pages.read(page.id)).version_id

    saved = await _write(services.pages, page.id, "# Emissão de apólice\n\n## Documentos\n- RG\n")

    assert saved.id != first
    current = await services.pages.read(page.id)
    assert (current.version_id, current.markdown) == (saved.id, "# Emissão de apólice\n\n## Documentos\n- RG\n")
    assert [(s.anchor, s.heading) for s in current.sections] == [("documentos", "Documentos")]


async def test_autosave_writes_no_version(services: Services, make_tree: MakeTree, session: AsyncSession) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)

    await _type(services.pages, page.id, "# Emissão de apólice\nUm\n")
    saved = await _type(services.pages, page.id, "# Emissão de apólice\nUm\nDois\n")

    current = await services.pages.read(page.id)
    assert (current.markdown, current.revision, current.saved_at) == (
        "# Emissão de apólice\nUm\nDois\n",
        saved.revision,
        saved.saved_at,
    )
    assert (saved.revision, current.version_id) == (opened.revision + 2, opened.version_id)
    assert await _stored(session, page.id) == [(opened.markdown, False)]


async def test_idle_save_cuts_the_previous_session(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)
    await _type(services.pages, page.id, "Primeira sessão\n")

    await _type(services.pages, page.id, "Segunda sessão\n", idle=0)

    assert await _stored(session, page.id) == [(opened.markdown, False), ("Primeira sessão\n", True)]
    assert (await services.pages.read(page.id)).markdown == "Segunda sessão\n"


async def test_leave_cuts_a_version(services: Services, make_tree: MakeTree, session: AsyncSession) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)
    await _type(services.pages, page.id, "Um\n")
    await _type(services.pages, page.id, "Um\nDois\n")

    await services.pages.cut(page.id)

    assert await _stored(session, page.id) == [(opened.markdown, False), ("Um\nDois\n", True)]
    [newest, _] = await services.pages.versions(page.id)
    assert newest.edit_started_at is not None and newest.edit_ended_at is not None
    assert newest.edit_started_at < newest.edit_ended_at <= newest.created_at


async def test_unchanged_cut_writes_nothing(services: Services, make_tree: MakeTree, session: AsyncSession) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)
    await _type(services.pages, page.id, opened.markdown)
    await services.pages.cut(page.id)
    await _type(services.pages, page.id, "Nova\n")
    await services.pages.cut(page.id)

    await services.pages.cut(page.id)

    assert await _stored(session, page.id) == [(opened.markdown, False), ("Nova\n", True)]


async def test_stale_revision_keeps_the_refused_text_as_version(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)
    first_tab = await _type(services.pages, page.id, "Aba 1\n")

    with pytest.raises(StalePage) as raised:
        await services.pages.put_text(page.id, PageTextPut(markdown="Aba 2\n", revision=opened.revision), IDLE)

    assert raised.value.details == {"markdown": "Aba 1\n", "revision": first_tab.revision}
    assert await _stored(session, page.id) == [(opened.markdown, False), ("Aba 2\n", False)]
    current = await services.pages.read(page.id)
    assert (current.markdown, current.revision) == ("Aba 1\n", first_tab.revision)


async def test_history_read_cuts_first(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    opened = await services.pages.read(page.id)
    await _type(services.pages, page.id, "Antes do histórico\n")

    history = await services.pages.versions(page.id)

    assert [v.id for v in history][1:] == [opened.version_id]
    assert (await services.pages.read(page.id)).version_id == history[0].id
    diff = await services.pages.diff(page.id, history[0].id)
    assert ("add", "Antes do histórico") in [(line.op, line.text) for line in diff.lines]


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


async def test_restore_sets_the_working_text(services: Services, make_tree: MakeTree, session: AsyncSession) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = await services.pages.read(page.id)
    await _write(services.pages, page.id, "Segunda\n")
    typing = await _type(services.pages, page.id, "Rascunho\n")

    restored = await services.pages.restore(page.id, first.version_id)

    assert (restored.markdown, restored.revision) == (first.markdown, typing.revision + 1)
    assert [text for text, _ in await _stored(session, page.id)] == [
        first.markdown,
        "Segunda\n",
        "Rascunho\n",
        first.markdown,
    ]
    assert (await services.pages.read(page.id)).markdown == first.markdown


async def test_history_newest_first_without_text(services: Services, make_tree: MakeTree) -> None:
    page = (await make_tree(TREE))[PAGE]
    first = (await services.pages.read(page.id)).version_id
    second = await _write(services.pages, page.id, "dois\n")
    third = await _write(services.pages, page.id, "três\n")

    history = await services.pages.versions(page.id)

    assert [v.id for v in history] == [third.id, second.id, first]
    assert history[0].created_at > history[1].created_at > history[2].created_at
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
    assert len(await services.pages.versions(emission.id)) == 3
    assert (await services.pages.read(unrelated)).version_id == unrelated_version.id


async def test_links_resolve_to_a_file(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Porto": ["Vistoria.md", "Edital.pdf"]})
    page = tree["Porto/Vistoria.md"]
    await _write(services.pages, page.id, "Ver [[Edital.pdf#p=3]].\n")

    assert (await services.pages.read(page.id)).links == {"edital.pdf": tree["Porto/Edital.pdf"].id}


async def test_file_rename_fixes_links_keeping_the_page(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Porto": ["Vistoria.md", "Edital.pdf"]})
    page = tree["Porto/Vistoria.md"]
    before = await _write(services.pages, page.id, "Ver [[Edital.pdf#p=3]].\n")

    await services.tree.rename(tree["Porto/Edital.pdf"].id, "Edital 2026.pdf")

    assert await _markdown(services.pages, page.id) == "Ver [[Edital 2026.pdf#p=3]].\n"
    assert before.id in [version.id for version in await services.pages.versions(page.id)]
    assert (await services.pages.read(page.id)).links == {"edital 2026.pdf": tree["Porto/Edital.pdf"].id}


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


async def test_rename_fixes_links_in_an_open_working_text(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await make_tree(TREE)
    page = tree["Porto/Vistoria.md"]
    opened = await services.pages.read(page.id)
    typing = await _type(services.pages, page.id, "Digitando [[Renovação]]\n")

    await services.tree.rename(tree["Bradesco/Residencial/Renovação.md"].id, "Renovação anual")

    current = await services.pages.read(page.id)
    assert (current.markdown, current.revision) == ("Digitando [[Renovação anual]]\n", typing.revision + 1)
    assert await _stored(session, page.id) == [(opened.markdown, False), ("Digitando [[Renovação anual]]\n", False)]
    with pytest.raises(StalePage):
        await services.pages.put_text(page.id, PageTextPut(markdown="Digitando mais\n", revision=typing.revision), IDLE)


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
async def committed_page(
    test_settings: Settings,
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], UUID, UUID]]:
    """A page written by sessions on connections of their own that commit, as parallel requests do; removed after."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with UnitOfWork(sessions) as uow:
        account = await uow.accounts.create(AccountCreate(email="paralelo@example.com", name="Ana"))
        organization = await uow.organizations.create_personal(account.id)
        uow.act_as(account.id)
        kb = await uow.kbs.create(KbCreate(name="Edições em paralelo", organization_id=organization.id))
        await uow.commit()
        page = await TreeService(uow).create(kb.id, NodeAdd(kind="page", title="Prazos"))
    yield sessions, page.id, account.id
    async with sessions() as session:
        of_base = select(Node.id).where(Node.kb_id == kb.id)
        await session.execute(delete(PageLink).where(PageLink.from_node_id.in_(of_base)))
        await session.execute(delete(PageDraft).where(PageDraft.node_id.in_(of_base)))
        await session.execute(delete(PageVersion).where(PageVersion.node_id.in_(of_base)))
        await session.execute(delete(Node).where(Node.kb_id == kb.id))
        await session.execute(delete(Kb).where(Kb.id == kb.id))
        await session.execute(delete(Organization).where(Organization.id == organization.id))
        await session.execute(delete(Account).where(Account.id == account.id))
        await session.commit()
    await engine.dispose()


async def _save_committed(
    sessions: async_sessionmaker[AsyncSession], account_id: UUID, node_id: UUID, revision: int, markdown: str
) -> PageTextSaved:
    async with UnitOfWork(sessions) as uow:
        uow.act_as(account_id)
        return await PageService(uow).put_text(node_id, PageTextPut(markdown=markdown, revision=revision), IDLE)


async def test_concurrent_saves_from_one_revision_give_one_stale_page(
    committed_page: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
) -> None:
    sessions, node_id, account_id = committed_page
    async with UnitOfWork(sessions) as uow:
        uow.act_as(account_id)
        revision = (await PageService(uow).read(node_id)).revision

    results = await asyncio.gather(
        *(_save_committed(sessions, account_id, node_id, revision, f"# Prazos\n{name}\n") for name in ("Ana", "Bruno")),
        return_exceptions=True,
    )

    assert sorted(isinstance(result, StalePage) for result in results) == [False, True]
    async with UnitOfWork(sessions) as uow:
        uow.act_as(account_id)
        # The empty first version, the refused text and, cut by the history, the text that won.
        assert len(await PageService(uow).versions(node_id)) == 3
