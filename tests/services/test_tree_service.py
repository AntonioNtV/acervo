from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError, StalePage, TitleTaken
from acervo.db.models import File, Node, PageLink, PageVersion
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeAdd, NodeEdit, NodeMove
from acervo.schemas.page import PageTextPut, PageTextSaved
from acervo.services.page_service import PageService
from acervo.services.tree_service import TreeService

MakeTree = Callable[..., Awaitable[Any]]
IDLE = 300


@dataclass
class Services:
    pages: PageService
    tree: TreeService


@dataclass
class Bases:
    """Base X with page "A", its sub-page "A1" and a PDF under "A", and page "B"; base Y with folder "Destino"."""

    x: Any
    y: Any
    a: UUID
    a1: UUID
    pdf: UUID
    b: UUID
    destination: UUID


@pytest.fixture
async def services(uow: UnitOfWork, session: AsyncSession, default_account_id: UUID) -> AsyncIterator[Services]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        uow.act_as(default_account_id)
        yield Services(PageService(uow), TreeService(uow))


@pytest.fixture
async def bases(
    services: Services, make_tree: MakeTree, make_account: MakeTree, uow: UnitOfWork, session: AsyncSession
) -> Bases:
    # The owner of both bases' Pessoal moves between them.
    uow.act_as((await make_account()).id)
    x = await make_tree({"Bradesco": ["CG 2026.pdf"], "A.md": None, "B.md": None}, name="X")
    y = await make_tree({"Destino": None}, name="Y")
    a = x["A.md"].id
    a1 = await services.tree.create(x.kb.id, NodeAdd(parent_id=a, kind="page", title="A1"))
    pdf = x["Bradesco/CG 2026.pdf"]
    pdf.parent_id = a
    await session.flush()
    return Bases(x=x, y=y, a=a, a1=a1.id, pdf=pdf.id, b=x["B.md"].id, destination=y["Destino"].id)


async def _type(pages: PageService, node_id: UUID, markdown: str) -> PageTextSaved:
    revision = (await pages.read(node_id)).revision
    return await pages.put_text(node_id, PageTextPut(markdown=markdown, revision=revision), IDLE)


async def _move_to_y(services: Services, bases: Bases, node_id: UUID | None = None) -> None:
    move = NodeMove(kb_id=bases.y.kb.id, parent_id=bases.destination)
    await services.tree.move(node_id or bases.a, move)


async def _versions(session: AsyncSession, node_id: UUID) -> list[str]:
    query = select(PageVersion.markdown).where(PageVersion.node_id == node_id).order_by(PageVersion.created_at)
    return list(await session.scalars(query))


async def test_move_to_another_base_takes_the_subtree(services: Services, bases: Bases, session: AsyncSession) -> None:
    trashed = await services.tree.create(bases.x.kb.id, NodeAdd(parent_id=bases.a1, kind="page", title="A2"))
    await services.tree.trash(trashed.id)
    await services.tree.edit(bases.a, NodeEdit(icon="📄"))
    await _type(services.pages, bases.a1, "Ver [[A]].\n")
    pdf = await session.scalar(select(File).where(File.node_id == bases.pdf))
    assert pdf is not None
    key = pdf.storage_key

    await _move_to_y(services, bases)

    rows = await session.scalars(
        select(Node)
        .where(Node.id.in_([bases.a, bases.a1, bases.pdf, trashed.id]))
        .execution_options(populate_existing=True)
    )
    assert {row.title: row.kb_id for row in rows} == {
        title: bases.y.kb.id for title in ("A", "A1", "CG 2026.pdf", "A2")
    }
    moved = await services.tree.detail(bases.a)
    assert (moved.parent_id, moved.icon, moved.path) == (bases.destination, "📄", "Destino/A")
    assert [n.title for n in await services.tree.children(bases.x.kb.id, None)] == ["Bradesco", "B"]
    assert {n.title for n in await services.tree.children(bases.y.kb.id, bases.a)} == {"A1", "CG 2026.pdf"}
    links = await session.scalars(select(PageLink.kb_id).where(PageLink.from_node_id == bases.a1))
    assert set(links) == {bases.y.kb.id}
    await session.refresh(pdf)
    assert pdf.storage_key == key


async def test_breaking_links_become_text_after_a_version(
    services: Services, bases: Bases, session: AsyncSession
) -> None:
    await _type(services.pages, bases.b, "Ver [[A]], [[ a ]] e [[A1]].\n")
    typing = await _type(services.pages, bases.b, "Ver [[A]], [[ a ]] e [[A1]], [[Bradesco]].\n")
    await _type(services.pages, bases.a1, "Volta para [[B]].\n")

    await _move_to_y(services, bases)

    b = await services.pages.read(bases.b)
    assert (b.markdown, b.revision) == ("Ver A, a e A1, [[Bradesco]].\n", typing.revision + 1)
    assert (await _versions(session, bases.b))[-2:] == [
        "Ver [[A]], [[ a ]] e [[A1]], [[Bradesco]].\n",
        "Ver A, a e A1, [[Bradesco]].\n",
    ]
    assert (await services.pages.read(bases.a1)).markdown == "Volta para B.\n"
    assert (await _versions(session, bases.a1))[-2:] == ["Volta para [[B]].\n", "Volta para B.\n"]
    with pytest.raises(StalePage):
        await services.pages.put_text(bases.b, PageTextPut(markdown="Mais\n", revision=typing.revision), IDLE)


async def test_links_inside_the_subtree_keep_working(services: Services, bases: Bases, session: AsyncSession) -> None:
    await _type(services.pages, bases.a1, "Ver [[A]].\n")
    await services.pages.cut(bases.a1)
    before = await services.pages.read(bases.a1)

    await _move_to_y(services, bases)

    after = await services.pages.read(bases.a1)
    assert (after.markdown, after.version_id, after.revision) == ("Ver [[A]].\n", before.version_id, before.revision)
    assert after.links == {"a": bases.a}


async def test_a_file_already_in_the_destination_refuses_the_move(
    services: Services, bases: Bases, make_tree: MakeTree, session: AsyncSession
) -> None:
    held = await make_tree({"Outro.pdf": None}, name="Z")
    copy = await session.scalar(select(File).where(File.node_id == held["Outro.pdf"].id))
    pdf = await session.scalar(select(File).where(File.node_id == bases.pdf))
    assert copy is not None and pdf is not None
    destination = await session.get_one(Node, held["Outro.pdf"].id)
    destination.kb_id = bases.y.kb.id
    copy.sha256 = pdf.sha256
    await session.flush()
    await _type(services.pages, bases.b, "Ver [[A]].\n")

    with pytest.raises(ConflictError) as refused:
        await _move_to_y(services, bases)

    assert (refused.value.code, refused.value.details) == ("conflict", {"files": ["CG 2026.pdf"]})
    rows = await session.scalars(
        select(Node.kb_id).where(Node.id.in_([bases.a, bases.a1, bases.pdf])).execution_options(populate_existing=True)
    )
    assert set(rows) == {bases.x.kb.id}
    assert (await services.pages.read(bases.b)).markdown == "Ver [[A]].\n"


async def test_a_trashed_file_does_not_refuse_the_move(
    services: Services, bases: Bases, make_tree: MakeTree, session: AsyncSession
) -> None:
    held = await make_tree({"Outro.pdf": None}, name="Z")
    copy = await session.scalar(select(File).where(File.node_id == held["Outro.pdf"].id))
    pdf = await session.scalar(select(File).where(File.node_id == bases.pdf))
    assert copy is not None and pdf is not None
    destination = await session.get_one(Node, held["Outro.pdf"].id)
    destination.kb_id = bases.y.kb.id
    copy.sha256 = pdf.sha256
    await session.flush()
    await services.tree.trash(bases.pdf)

    await _move_to_y(services, bases)

    rows = await session.scalars(
        select(Node.kb_id).where(Node.id.in_([bases.a, bases.a1, bases.pdf])).execution_options(populate_existing=True)
    )
    assert set(rows) == {bases.y.kb.id}


async def test_title_clash_at_destination(services: Services, bases: Bases) -> None:
    await services.tree.create(bases.y.kb.id, NodeAdd(parent_id=bases.destination, kind="page", title="a"))

    with pytest.raises(TitleTaken):
        await _move_to_y(services, bases)

    assert (await services.tree.detail(bases.a)).kb_id == bases.x.kb.id
