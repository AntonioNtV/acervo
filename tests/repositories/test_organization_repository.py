from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError
from acervo.db.models import Kb, Organization, PageAttachment
from acervo.repositories.account import AccountRepository
from acervo.repositories.membership import MembershipRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.schemas.account import AccountCreate, AccountRead
from acervo.schemas.organization import MembershipCreate, OrganizationCreate, OrganizationRecord

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
MakeTree = Callable[..., Awaitable[Any]]


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


async def test_delete_removes_the_bases_and_keeps_bytes_another_base_uses(
    session: AsyncSession, make_account: MakeAccount, make_organization: MakeOrganization, make_tree: MakeTree
) -> None:
    ana = await make_account()
    team = await make_organization(ana.id)
    tree = await make_tree({"Docs": ["Manual.md", "CG 2026.pdf"]}, organization=team.id)
    page = tree["Docs/Manual.md"]
    page.cover = "image:cover1"
    session.add_all(
        [
            PageAttachment(page_id=page.id, name="a.txt", sha256="only-here", mime="text/plain", size=5),
            PageAttachment(page_id=page.id, name="b.txt", sha256="shared", mime="text/plain", size=5),
        ]
    )
    other = (await make_tree(["Outra.md"]))["Outra.md"]
    session.add(PageAttachment(page_id=other.id, name="b.txt", sha256="shared", mime="text/plain", size=5))
    await session.flush()

    files, covers, attachments = await OrganizationRepository(session).delete(team.id)

    assert (len(files), covers, attachments) == (1, ["cover1"], ["only-here"])
    assert await session.scalar(select(func.count()).select_from(Kb).where(Kb.organization_id == team.id)) == 0
    assert await session.get(Organization, team.id) is None
