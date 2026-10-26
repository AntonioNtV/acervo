from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.node import NodeCreate
from acervo.schemas.organization import BaseMemberCreate
from tests.conftest import Tree


@pytest.fixture
async def two_organizations(
    session: AsyncSession,
    make_account: Callable[..., Awaitable[AccountRead]],
    make_tree: Callable[..., Awaitable[Tree]],
) -> tuple[AccountRead, Tree, Tree]:
    """Ana's base in her Pessoal, and Bia's in hers."""
    ana = await make_account()
    bia = await make_account(email="bia@example.com", name="Bia")
    bia_personal = await OrganizationRepository(session).get_by(personal_of=bia.id)
    assert bia_personal is not None
    ana_tree = await make_tree({"Ana": ["Emissão.md"]}, name="Base da Ana")
    bia_tree = await make_tree({"Bia": ["Sinistro.md"]}, name="Base da Bia", organization=bia_personal.id)
    return ana, ana_tree, bia_tree


async def _node_kbs(uow: UnitOfWork) -> set[UUID]:
    rows = await uow._session.execute(text("select kb_id from acervo.node"))
    return {row.kb_id for row in rows}


async def test_a_raw_select_sees_none_of_the_other_organization(
    uow: UnitOfWork, two_organizations: tuple[AccountRead, Tree, Tree]
) -> None:
    ana, ana_tree, _ = two_organizations
    async with uow:
        uow.act_as(ana.id)
        assert await _node_kbs(uow) == {ana_tree.kb.id}


async def test_a_node_cannot_be_written_into_the_other_organization(
    uow: UnitOfWork, two_organizations: tuple[AccountRead, Tree, Tree]
) -> None:
    ana, _, bia_tree = two_organizations
    async with uow:
        uow.act_as(ana.id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await uow.nodes.create(NodeCreate(kb_id=bia_tree.kb.id, parent_id=None, kind="page", title="X", sort="z"))


async def test_no_account_sees_no_base(uow: UnitOfWork, two_organizations: tuple[AccountRead, Tree, Tree]) -> None:
    async with uow:
        assert await _node_kbs(uow) == set()
        assert (await uow._session.execute(text("select count(*) from acervo.kb"))).scalar_one() == 0


async def test_a_base_shared_from_another_pessoal_is_visible(
    uow: UnitOfWork, session: AsyncSession, two_organizations: tuple[AccountRead, Tree, Tree]
) -> None:
    ana, ana_tree, bia_tree = two_organizations
    async with uow:
        await uow.base_members.create(BaseMemberCreate(kb_id=bia_tree.kb.id, account_id=ana.id, role="reader"))
        uow.act_as(ana.id)
        assert await _node_kbs(uow) == {ana_tree.kb.id, bia_tree.kb.id}
