from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeAdd
from acervo.schemas.page import PageTextPut
from acervo.services.duplicate_service import DuplicateService
from acervo.services.page_service import PageService
from acervo.services.tree_service import TreeService

MakeTree = Callable[..., Awaitable[Any]]
IDLE = 300


@dataclass
class Services:
    duplicate: DuplicateService
    pages: PageService
    tree: TreeService


@pytest.fixture
async def services(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[Services]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield Services(DuplicateService(uow), PageService(uow), TreeService(uow))


async def test_copies_the_working_text_and_sub_pages_not_files(
    services: Services, make_tree: MakeTree, session: AsyncSession
) -> None:
    tree = await make_tree({"Bradesco": ["Emissão.md", "CG 2026.pdf"]})
    emissao = tree["Bradesco/Emissão.md"]
    tree["Bradesco/CG 2026.pdf"].parent_id = emissao.id
    await session.flush()
    first = await services.tree.create(tree.kb.id, NodeAdd(parent_id=emissao.id, kind="page", title="Prazos"))
    second = await services.tree.create(tree.kb.id, NodeAdd(parent_id=emissao.id, kind="page", title="Documentos"))
    await services.pages.put_text(emissao.id, PageTextPut(markdown="Ver [[Prazos]].", revision=0), IDLE)
    await services.pages.put_text(second.id, PageTextPut(markdown="RG e CPF.", revision=0), IDLE)

    copy = await services.duplicate.duplicate(emissao.id)

    assert (copy.title, copy.parent_id) == ("Emissão (cópia)", tree["Bradesco"].id)
    page = await services.pages.read(copy.id)
    assert page.markdown == "Ver [[Prazos]]."
    children = await services.tree.children(tree.kb.id, copy.id)
    assert [(c.kind, c.title) for c in children] == [("page", "Prazos (cópia)"), ("page", "Documentos (cópia)")]
    assert [(await services.pages.read(c.id)).markdown for c in children] == ["", "RG e CPF."]
    assert {c.id for c in children}.isdisjoint({first.id, second.id})
    assert set(page.links) == {"prazos"}


async def test_sub_page_copies_get_the_suffix_and_links_stay_unique(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Emissão.md"]})
    emissao = tree["Bradesco/Emissão.md"]
    prazos = await services.tree.create(tree.kb.id, NodeAdd(parent_id=emissao.id, kind="page", title="Prazos"))
    taken = await services.tree.create(tree.kb.id, NodeAdd(parent_id=emissao.id, kind="page", title="Prazos (cópia)"))
    documentos = await services.tree.create(tree.kb.id, NodeAdd(parent_id=emissao.id, kind="page", title="Documentos"))
    await services.pages.put_text(documentos.id, PageTextPut(markdown="Ver [[Prazos]].", revision=0), IDLE)

    copy = await services.duplicate.duplicate(emissao.id)

    children = await services.tree.children(tree.kb.id, copy.id)
    assert [c.title for c in children] == ["Prazos (cópia)", "Prazos (cópia) (cópia)", "Documentos (cópia)"]
    assert {c.id for c in children}.isdisjoint({prazos.id, taken.id, documentos.id})
    assert (await services.pages.read(children[2].id)).links == {"prazos": prazos.id}
    mentions = await services.pages.mentions(prazos.id)
    assert sorted(m.node.path for m in mentions) == [
        "Bradesco/Emissão (cópia)/Documentos (cópia)",
        "Bradesco/Emissão/Documentos",
    ]


async def test_title_counts_up_when_taken(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["Emissão.md"]})
    emissao = tree["Bradesco/Emissão.md"].id

    titles = [(await services.duplicate.duplicate(emissao)).title for _ in range(3)]

    assert titles == ["Emissão (cópia)", "Emissão (cópia 2)", "Emissão (cópia 3)"]


async def test_copy_sits_after_the_original(services: Services, make_tree: MakeTree) -> None:
    tree = await make_tree({"Bradesco": ["A.md", "Emissão.md", "B.md"]})

    await services.duplicate.duplicate(tree["Bradesco/Emissão.md"].id)

    children = await services.tree.children(tree.kb.id, tree["Bradesco"].id)
    assert [c.title for c in children] == ["A", "Emissão", "Emissão (cópia)", "B"]
