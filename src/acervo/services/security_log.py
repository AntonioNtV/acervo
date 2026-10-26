from typing import Any
from uuid import UUID

from acervo.repositories.uow import UnitOfWork
from acervo.schemas.security import SecurityEventCreate, SecurityEventKind, SecurityEventRecord


class SecurityLog:
    """The one place the activity of an account and the audit of an organization are written."""

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
