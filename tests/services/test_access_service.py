from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ForbiddenError
from acervo.db.models import Kb
from acervo.repositories.base_member import BaseMemberRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import BaseMemberCreate, BaseRole, GeneralAccess, OrganizationRecord
from acervo.services.access_service import AccessService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Any]]


@pytest.fixture
async def access(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[AccessService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield AccessService(uow)


@pytest.fixture
async def people(make_account: MakeAccount) -> dict[str, UUID]:
    """Ana is the default account, so `make_tree` without an organization builds in her Pessoal."""
    names = ("Ana", "Bia", "Caio", "Dani")
    return {name: (await make_account(email=f"{name.lower()}@example.com", name=name)).id for name in names}


@pytest.fixture
async def team(people: dict[str, UUID], make_organization: MakeOrganization) -> OrganizationRecord:
    """Seguros SA: Ana Owner, Bia Admin, Caio Membro; Dani is not in it."""
    return await make_organization(people["Ana"], members={people["Bia"]: "admin", people["Caio"]: "member"})


async def _base(session: AsyncSession, make_tree: MakeTree, team: OrganizationRecord, general: GeneralAccess) -> UUID:
    kb_id: UUID = (await make_tree(None, organization=team.id)).kb.id
    await session.execute(update(Kb).where(Kb.id == kb_id).values(general_access=general))
    return kb_id


async def _add(session: AsyncSession, kb_id: UUID, account_id: UUID, role: BaseRole) -> None:
    await BaseMemberRepository(session).create(BaseMemberCreate(kb_id=kb_id, account_id=account_id, role=role))


async def test_org_owner_and_admin_are_admin_of_a_restricted_base(
    access: AccessService, session: AsyncSession, make_tree: MakeTree, team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    kb_id = await _base(session, make_tree, team, "none")

    assert [await access.base_role(people[name], kb_id) for name in ("Ana", "Bia", "Caio")] == ["admin", "admin", None]
    assert await access.visible_kb_ids(people["Bia"], team.id) == {kb_id}
    assert await access.visible_kb_ids(people["Caio"]) == set()


async def test_member_gets_the_general_access(
    access: AccessService, session: AsyncSession, make_tree: MakeTree, team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    kb_id = await _base(session, make_tree, team, "reader")

    assert await access.base_role(people["Caio"], kb_id) == "reader"
    assert await access.require_base(people["Caio"], kb_id, "reader") == "reader"
    with pytest.raises(ForbiddenError):
        await access.require_base(people["Caio"], kb_id, "editor")


async def test_base_role_beats_the_general_access(
    access: AccessService, session: AsyncSession, make_tree: MakeTree, team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    kb_id = await _base(session, make_tree, team, "editor")
    await _add(session, kb_id, people["Caio"], "admin")

    assert await access.base_role(people["Caio"], kb_id) == "admin"


async def test_outsider_sees_nothing_and_a_guest_only_their_base_role(
    access: AccessService, session: AsyncSession, make_tree: MakeTree, team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    kb_id = await _base(session, make_tree, team, "editor")

    assert (await access.base_role(people["Dani"], kb_id), await access.org_role(people["Dani"], team.id)) == (
        None,
        None,
    )
    assert await access.visible_kb_ids(people["Dani"]) == set()
    with pytest.raises(ForbiddenError):
        await access.require_org(people["Dani"], team.id, "member")

    await _add(session, kb_id, people["Dani"], "reader")
    assert await access.base_role(people["Dani"], kb_id) == "reader"
    assert await access.visible_kb_ids(people["Dani"]) == {kb_id}


async def test_pessoal_owner_is_admin_of_its_bases(
    access: AccessService, make_tree: MakeTree, people: dict[str, UUID]
) -> None:
    kb_id = (await make_tree(None)).kb.id

    assert await access.base_role(people["Ana"], kb_id) == "admin"
    assert await access.base_role(people["Bia"], kb_id) is None
