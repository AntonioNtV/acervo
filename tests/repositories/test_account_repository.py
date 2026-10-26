from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError
from acervo.repositories.account import AccountRepository
from acervo.schemas.account import AccountCreate, AccountRead, AccountUpdate
from acervo.schemas.organization import OrganizationRecord

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]


@pytest.fixture
def accounts(session: AsyncSession) -> AccountRepository:
    return AccountRepository(session)


async def test_email_is_unique_ignoring_case(accounts: AccountRepository, session: AsyncSession) -> None:
    ana = await accounts.create(AccountCreate(email="Ana.Souza@Example.com", name="Ana"))

    found = await accounts.by_email("ana.souza@example.COM")
    assert found is not None
    assert (found.id, found.email) == (ana.id, "Ana.Souza@Example.com")
    async with session.begin_nested():
        with pytest.raises(ConflictError) as refused:
            await accounts.create(AccountCreate(email="ANA.SOUZA@example.com", name="Outra"))
    assert refused.value.details == {"constraint": "uq_account_email_lower"}


async def test_google_sub_is_unique(accounts: AccountRepository, session: AsyncSession) -> None:
    ana = await accounts.create(AccountCreate(email="ana@example.com", name="Ana", google_sub="sub-1"))
    bia = await accounts.create(AccountCreate(email="bia@example.com", name="Bia"))

    async with session.begin_nested():
        with pytest.raises(ConflictError) as refused:
            await accounts.update(bia.id, AccountUpdate(google_sub="sub-1"))
    assert refused.value.details == {"constraint": "uq_account_google_sub"}
    assert await accounts.get_by(google_sub="sub-1") == ana


async def test_sole_owned_lists_the_teams_where_the_account_is_the_only_owner(
    session: AsyncSession, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com")
    alone = await make_organization(ana.id, name="Só da Ana", members={bia.id: "admin"})
    await make_organization(ana.id, name="Duas owners", members={bia.id: "owner"})
    await make_organization(bia.id, name="Da Bia", members={ana.id: "member"})

    assert await AccountRepository(session).sole_owned(ana.id) == [alone.id]
