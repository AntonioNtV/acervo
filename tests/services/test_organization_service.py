from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ForbiddenError, LastOwner
from acervo.core.settings import Settings
from acervo.repositories.base_member import BaseMemberRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import BaseMemberCreate, OrganizationRecord
from acervo.services.access_service import AccessService
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.organization_service import OrganizationService
from acervo.services.storage import Storage

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Any]]


@pytest.fixture
async def service(
    uow: UnitOfWork, session: AsyncSession, storage: Settings, fake_mailer: FakeMailer
) -> AsyncIterator[OrganizationService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield OrganizationService(uow, Storage(storage), fake_mailer, AccessService(uow))


@pytest.fixture
async def people(make_account: MakeAccount) -> dict[str, UUID]:
    names = ("Ana", "Bia", "Caio")
    return {name: (await make_account(email=f"{name.lower()}@example.com", name=name)).id for name in names}


@pytest.fixture
async def team(people: dict[str, UUID], make_organization: MakeOrganization) -> OrganizationRecord:
    """Seguros SA: Ana Owner, Bia Admin, Caio Membro."""
    return await make_organization(people["Ana"], members={people["Bia"]: "admin", people["Caio"]: "member"})


async def test_the_last_owner_cannot_be_demoted_removed_or_leave(
    service: OrganizationService, team: OrganizationRecord, people: dict[str, UUID], fake_mailer: FakeMailer
) -> None:
    ana = people["Ana"]

    for attempt in (
        service.change_role(ana, team.id, ana, "admin"),
        service.remove(ana, team.id, ana),
        service.leave(ana, team.id),
    ):
        with pytest.raises(LastOwner):
            await attempt

    await service.change_role(ana, team.id, people["Bia"], "owner")
    await service.leave(ana, team.id)
    assert [m.name for m in await service.members(people["Bia"], team.id)] == ["Bia", "Caio"]
    assert fake_mailer.sent[-1].template == MailTemplate.ROLE_CHANGED


async def test_an_admin_cannot_demote_remove_or_make_an_owner(
    service: OrganizationService, team: OrganizationRecord, people: dict[str, UUID], fake_mailer: FakeMailer
) -> None:
    bia = people["Bia"]

    for attempt in (
        service.change_role(bia, team.id, people["Ana"], "member"),
        service.remove(bia, team.id, people["Ana"]),
        service.change_role(bia, team.id, people["Caio"], "owner"),
    ):
        with pytest.raises(ForbiddenError):
            await attempt

    assert fake_mailer.sent == []


async def test_a_pessoal_has_no_members_to_list_and_cannot_be_left(
    service: OrganizationService, session: AsyncSession, people: dict[str, UUID]
) -> None:
    personal = await OrganizationRepository(session).get_by(personal_of=people["Ana"])
    assert personal is not None

    with pytest.raises(ForbiddenError):
        await service.members(people["Ana"], personal.id)
    with pytest.raises(ForbiddenError):
        await service.leave(people["Ana"], personal.id)


async def test_leaving_drops_the_membership_and_the_base_roles_in_it(
    service: OrganizationService,
    session: AsyncSession,
    make_tree: MakeTree,
    team: OrganizationRecord,
    people: dict[str, UUID],
) -> None:
    caio = people["Caio"]
    kb_id = (await make_tree(None, organization=team.id)).kb.id
    await BaseMemberRepository(session).create(BaseMemberCreate(kb_id=kb_id, account_id=caio, role="editor"))

    await service.leave(caio, team.id)

    assert [o.personal for o in await service.mine(caio)] == [True]
    assert await BaseMemberRepository(session).get_by(kb_id=kb_id, account_id=caio) is None
