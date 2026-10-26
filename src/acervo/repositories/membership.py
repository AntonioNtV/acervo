from uuid import UUID

from sqlalchemy import delete, func, select

from acervo.db.models.membership import Membership
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import MembershipCreate, MembershipRecord, MembershipUpdate


class MembershipRepository(BaseRepository[Membership, MembershipRecord, MembershipCreate, MembershipUpdate]):
    orm_model = Membership
    read_schema = MembershipRecord

    async def of_account(self, account_id: UUID) -> list[MembershipRecord]:
        rows = await self._session.scalars(self._select().where(Membership.account_id == account_id))
        return [self._to_read(row) for row in rows]

    async def of_organization(self, organization_id: UUID) -> list[MembershipRecord]:
        rows = await self._session.scalars(self._select().where(Membership.organization_id == organization_id))
        return [self._to_read(row) for row in rows]

    async def lock(self, organization_id: UUID) -> None:
        """Serializes changes to one organization's members until the transaction ends."""
        key = int.from_bytes(organization_id.bytes[:8], signed=True)
        await self._session.execute(select(func.pg_advisory_xact_lock(key)))

    async def delete(self, membership_id: UUID) -> None:
        await self._session.execute(delete(Membership).where(Membership.id == membership_id))
