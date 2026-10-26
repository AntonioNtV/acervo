from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ForbiddenError, NotFoundError, ValidationError
from acervo.repositories.base_member import BaseMemberRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.kb import KbCreate, KbEdit
from acervo.schemas.organization import BaseMemberCreate, OrganizationChange, OrganizationRecord
from acervo.services.base_service import BaseService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]


@pytest.fixture
async def people(make_account: MakeAccount) -> dict[str, UUID]:
    names = ("Ana", "Bia", "Caio", "Dani")
    return {name: (await make_account(email=f"{name.lower()}@example.com", name=name)).id for name in names}


@pytest.fixture
async def team(people: dict[str, UUID], make_organization: MakeOrganization) -> OrganizationRecord:
    """Seguros SA: Ana Owner, Bia Admin, Caio Membro; Dani is not in it."""
    return await make_organization(people["Ana"], members={people["Bia"]: "admin", people["Caio"]: "member"})


@pytest.fixture
async def as_(uow: UnitOfWork, session: AsyncSession, people: dict[str, UUID]) -> AsyncIterator[Callable[[str], Any]]:
    """The base service acting as one of `people`; `session` closes after the unit of work, whose savepoint it holds."""
    async with uow:

        def act(name: str) -> BaseService:
            uow.act_as(people[name])
            return BaseService(uow)

        yield act


def _ids(kbs: list[Any]) -> dict[UUID, tuple[str | None, str | None]]:
    return {kb.id: (kb.my_role, kb.shared_by) for kb in kbs}


async def test_restricted_base_hidden_from_a_member_visible_to_an_org_admin(
    as_: Callable[[str], BaseService], team: OrganizationRecord
) -> None:
    kb = await as_("Caio").create(KbCreate(name="Sinistros", organization_id=team.id))
    assert (kb.general_access, kb.my_role) == ("editor", "admin")
    await as_("Ana").set_general_access(kb.id, "none")
    other = await as_("Ana").create(KbCreate(name="Jurídico", organization_id=team.id))
    await as_("Ana").set_general_access(other.id, "none")

    assert _ids(await as_("Caio").list(organization_id=team.id)) == {kb.id: ("admin", None)}
    assert _ids(await as_("Bia").list(organization_id=team.id)) == {kb.id: ("admin", None), other.id: ("admin", None)}
    with pytest.raises(ForbiddenError):
        await as_("Dani").list(organization_id=team.id)


async def test_a_member_creates_a_base_that_starts_restricted(
    as_: Callable[[str], BaseService], session: AsyncSession, team: OrganizationRecord
) -> None:
    await OrganizationRepository(session).update(team.id, OrganizationChange(new_base_access="none"))

    kb = await as_("Caio").create(KbCreate(name="Sinistros", organization_id=team.id))

    assert (kb.general_access, kb.my_role) == ("none", "admin")
    assert _ids(await as_("Caio").list(organization_id=team.id)) == {kb.id: ("admin", None)}


async def test_pessoal_lists_the_bases_shared_with_a_guest(
    as_: Callable[[str], BaseService], session: AsyncSession, team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    pessoal = await as_("Dani").create(KbCreate(name="Receitas"))
    team_kb = await as_("Ana").create(KbCreate(name="Sinistros", organization_id=team.id))
    for kb_id in (pessoal.id, team_kb.id):
        await BaseMemberRepository(session).create(
            BaseMemberCreate(kb_id=kb_id, account_id=people["Caio"], role="reader")
        )

    assert pessoal.general_access == "none"
    assert _ids(await as_("Caio").list()) == {pessoal.id: ("reader", "Dani")}
    assert _ids(await as_("Bia").list()) == {}
    # Row-level security hides Dani's Pessoal from Ana, so it is not even there for her.
    with pytest.raises(NotFoundError):
        await as_("Ana").put_member(pessoal.id, people["Bia"], "reader")

    await BaseMemberRepository(session).create(
        BaseMemberCreate(kb_id=team_kb.id, account_id=people["Dani"], role="editor")
    )
    assert _ids(await as_("Dani").list()) == {pessoal.id: ("admin", None), team_kb.id: ("editor", "Seguros SA")}


async def test_general_access_change(as_: Callable[[str], BaseService], team: OrganizationRecord) -> None:
    kb = await as_("Bia").create(KbCreate(name="Sinistros", organization_id=team.id))

    access = await as_("Bia").set_general_access(kb.id, "reader")

    assert (access.general_access, [m.name for m in access.members]) == ("reader", ["Bia"])
    assert _ids(await as_("Caio").list(organization_id=team.id)) == {kb.id: ("reader", None)}
    with pytest.raises(ForbiddenError):
        await as_("Caio").set_general_access(kb.id, "editor")
    pessoal = await as_("Caio").create(KbCreate(name="Notas"))
    with pytest.raises(ValidationError):
        await as_("Caio").set_general_access(pessoal.id, "reader")


async def test_only_a_base_admin_trashes_the_base(
    as_: Callable[[str], BaseService], team: OrganizationRecord, people: dict[str, UUID]
) -> None:
    kb = await as_("Ana").create(KbCreate(name="Sinistros", organization_id=team.id))

    with pytest.raises(ForbiddenError):
        await as_("Caio").trash(kb.id)
    with pytest.raises(ForbiddenError):
        await as_("Caio").update(kb.id, KbEdit(name="Outro"))

    await as_("Ana").put_member(kb.id, people["Caio"], "admin")
    assert (await as_("Caio").trash(kb.id)).my_role == "admin"
    await as_("Ana").restore(kb.id)
    await as_("Ana").put_member(kb.id, people["Caio"], "editor")
    await as_("Ana").trash(kb.id)
    # The Lixeira lists a base only to who can restore it.
    assert (await as_("Caio").trashed(team.id), [t.id for t in await as_("Bia").trashed(team.id)]) == ([], [kb.id])
    with pytest.raises(ForbiddenError):
        await as_("Caio").restore(kb.id)
