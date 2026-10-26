from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRecord
from acervo.schemas.security import (
    AuditEventRead,
    SecurityEventCreate,
    SecurityEventKind,
    SecurityEventRead,
    SecurityEventRecord,
)
from acervo.services.access_service import AccessService

# What Atividade and Auditoria show; the rows stay (history rule).
SHOWN = timedelta(days=90)


class SecurityLog:
    """The one place the activity of an account and the audit of an organization are written and read."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def record(
        self,
        kind: SecurityEventKind,
        *,
        account_id: UUID | None = None,
        organization_id: UUID | None = None,
        actor_id: UUID | None = None,
        data: dict[str, Any] | None = None,
        user_agent: str | None = None,
    ) -> SecurityEventRecord:
        """Adds the event to the caller's transaction, so it is kept only if the change it tells of is."""
        event = SecurityEventCreate(
            account_id=account_id,
            organization_id=organization_id,
            actor_id=actor_id,
            kind=kind,
            data=data or {},
            user_agent=user_agent,
        )
        return await self._uow.security_events.create(event)

    async def activity(self, account_id: UUID) -> list[SecurityEventRead]:
        """The account's last 90 days, newest first."""
        events = await self._uow.security_events.of_account(account_id, datetime.now(UTC) - SHOWN)
        return [_activity_line(event) for event in events]

    async def audit(self, account_id: UUID, organization_id: UUID) -> list[AuditEventRead]:
        """The organization's last 90 days, newest first; for its Owners and Admins."""
        await AccessService(self._uow).require_org(account_id, organization_id, "admin")
        events = await self._uow.security_events.of_organization(organization_id, datetime.now(UTC) - SHOWN)
        actors: dict[UUID, AccountRecord] = {}
        for actor_id in {event.actor_id for event in events} - {None}:
            assert actor_id is not None
            actors[actor_id] = await self._uow.accounts.get(actor_id)
        return [
            AuditEventRead(
                id=event.id,
                kind=event.kind,
                data=event.data,
                actor_id=event.actor_id,
                actor_name=actors[event.actor_id].name if event.actor_id else None,
                actor_email=actors[event.actor_id].email if event.actor_id else None,
                created_at=event.created_at,
            )
            for event in events
        ]


def _activity_line(event: SecurityEventRecord) -> SecurityEventRead:
    browser, system = device(event.user_agent)
    return SecurityEventRead(
        id=event.id, kind=event.kind, data=event.data, browser=browser, system=system, created_at=event.created_at
    )
