from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import OrganizationRecord
from acervo.schemas.security import SecurityEventKind
from acervo.services.security_log import SecurityLog

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
SINCE = datetime.now(UTC) - timedelta(days=90)


async def test_lists_an_accounts_events_newest_first(uow: UnitOfWork, make_account: MakeAccount) -> None:
    ana, bruno = await make_account(), await make_account(email="bruno@example.com", name="Bruno")
    async with uow:
        log = SecurityLog(uow)
        await log.record(SecurityEventKind.SIGNED_IN, account_id=ana.id, data={"method": "password"}, user_agent="UA")
        await log.record(SecurityEventKind.PASSKEY_ADDED, account_id=ana.id, data={"name": "1Password"})
        await log.record(SecurityEventKind.SIGNED_IN, account_id=bruno.id)
        await uow.commit()

        events = await uow.security_events.of_account(ana.id, SINCE)

    assert [(event.kind, event.data) for event in events] == [
        (SecurityEventKind.PASSKEY_ADDED, {"name": "1Password"}),
        (SecurityEventKind.SIGNED_IN, {"method": "password"}),
    ]
    assert events[1].user_agent == "UA"


async def test_an_organizations_audit_lists_only_its_own(
    uow: UnitOfWork, make_account: MakeAccount, make_organization: MakeOrganization
) -> None:
    ana = await make_account()
    seguros, corretora = await make_organization(ana.id), await make_organization(ana.id, name="Corretora")
    async with uow:
        log = SecurityLog(uow)
        await log.record(SecurityEventKind.TWO_FACTOR_REQUIRED, organization_id=seguros.id, actor_id=ana.id)
        await log.record(SecurityEventKind.BASE_CREATED, organization_id=corretora.id, actor_id=ana.id)
        await log.record(SecurityEventKind.PASSWORD_CHANGED, account_id=ana.id)
        await uow.commit()

        audit = await uow.security_events.of_organization(seguros.id, SINCE)

    assert [(event.kind, event.actor_id) for event in audit] == [(SecurityEventKind.TWO_FACTOR_REQUIRED, ana.id)]
