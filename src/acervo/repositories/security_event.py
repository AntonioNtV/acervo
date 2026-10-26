from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement

from acervo.db.models.security_event import SecurityEvent
from acervo.repositories.base import BaseRepository
from acervo.schemas.security import SecurityEventCreate, SecurityEventRecord


class SecurityEventRepository(BaseRepository[SecurityEvent, SecurityEventRecord, SecurityEventCreate, BaseModel]):
    orm_model = SecurityEvent
    read_schema = SecurityEventRecord

    async def of_account(self, account_id: UUID, since: datetime) -> list[SecurityEventRecord]:
        """The account's activity from `since`, newest first."""
        return await self._newest_first(SecurityEvent.account_id == account_id, since)

    async def of_organization(self, organization_id: UUID, since: datetime) -> list[SecurityEventRecord]:
        """The organization's audit from `since`, newest first."""
        return await self._newest_first(SecurityEvent.organization_id == organization_id, since)

    async def _newest_first(self, owner: ColumnElement[bool], since: datetime) -> list[SecurityEventRecord]:
        # Events of one transaction share now(); their uuid7 ids keep the order they were recorded in.
        query = (
            self._select()
            .where(owner, SecurityEvent.created_at >= since)
            .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
        )
        return [self._to_read(event) for event in await self._session.scalars(query)]
