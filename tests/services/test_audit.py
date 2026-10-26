from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ForbiddenError
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.kb import KbCreate
from acervo.schemas.organization import OrganizationRecord
from acervo.schemas.security import SecurityEventKind
from acervo.services.access_service import AccessService
from acervo.services.base_service import BaseService
from acervo.services.mailer import FakeMailer
from acervo.services.organization_service import OrganizationService
from acervo.services.security_log import SecurityLog
from acervo.services.storage import Storage

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]


async def test_the_audit_lists_the_organizations_events_only_to_owners_and_admins(
    uow: UnitOfWork,
    session: AsyncSession,
    storage: Settings,
    fake_mailer: FakeMailer,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
) -> None:
    ana, bia = await make_account(), await make_account(email="bia@example.com", name="Bia")
    caio = await make_account(email="caio@example.com", name="Caio")
    seguros = await make_organization(ana.id, members={bia.id: "admin", caio.id: "member"})
    corretora = await make_organization(ana.id, name="Corretora")
    # `session` closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        uow.act_as(ana.id)
        organizations = OrganizationService(uow, Storage(storage), fake_mailer, AccessService(uow))
        kb = await BaseService(uow).create(KbCreate(name="Sinistros", organization_id=seguros.id))
        await BaseService(uow).create(KbCreate(name="Outra", organization_id=corretora.id))
        await organizations.change_role(ana.id, seguros.id, caio.id, "admin")
        await organizations.remove(ana.id, seguros.id, caio.id)

        log = SecurityLog(uow)
        by_owner = await log.audit(ana.id, seguros.id)
        by_admin = await log.audit(bia.id, seguros.id)
        with pytest.raises(ForbiddenError):
            await log.audit(caio.id, seguros.id)

    assert [(e.kind, e.actor_name, e.data) for e in by_owner] == [
        (SecurityEventKind.REMOVED, "Ana", {"member": "caio@example.com", "role": "admin"}),
        (SecurityEventKind.ROLE_CHANGED, "Ana", {"member": "caio@example.com", "role": "admin", "old_role": "member"}),
        (SecurityEventKind.BASE_CREATED, "Ana", {"base": kb.name}),
    ]
    assert by_admin == by_owner
