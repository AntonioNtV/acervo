import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError
from acervo.repositories.account import AccountRepository
from acervo.repositories.membership import MembershipRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.schemas.account import AccountCreate
from acervo.schemas.organization import MembershipCreate, OrganizationCreate


async def test_one_personal_per_account_owned_by_it(session: AsyncSession) -> None:
    organizations, memberships = OrganizationRepository(session), MembershipRepository(session)
    ana = await AccountRepository(session).create(AccountCreate(email="ana@example.com", name="Ana"))

    personal = await organizations.create_personal(ana.id)

    owner = await memberships.get_by(organization_id=personal.id, account_id=ana.id)
    assert (personal.personal_of, owner and owner.role) == (ana.id, "owner")
    async with session.begin_nested():
        with pytest.raises(ConflictError) as refused:
            await organizations.create_personal(ana.id)
    assert refused.value.details == {"constraint": "uq_organization_personal_of"}


async def test_membership_is_unique(session: AsyncSession) -> None:
    memberships = MembershipRepository(session)
    ana = await AccountRepository(session).create(AccountCreate(email="ana@example.com", name="Ana"))
    team = await OrganizationRepository(session).create(OrganizationCreate(name="Seguros SA"))
    await memberships.create(MembershipCreate(organization_id=team.id, account_id=ana.id, role="member"))

    async with session.begin_nested():
        with pytest.raises(ConflictError) as refused:
            await memberships.create(MembershipCreate(organization_id=team.id, account_id=ana.id, role="admin"))
    assert refused.value.details == {"constraint": "uq_membership_organization_id_account_id"}
