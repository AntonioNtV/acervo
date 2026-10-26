from uuid import UUID

from acervo.db.models.membership import Membership
from acervo.db.models.organization import Organization
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import OrganizationChange, OrganizationCreate, OrganizationRecord


class OrganizationRepository(BaseRepository[Organization, OrganizationRecord, OrganizationCreate, OrganizationChange]):
    orm_model = Organization
    read_schema = OrganizationRecord

    async def create_personal(self, account_id: UUID) -> OrganizationRecord:
        """The account's Pessoal, with the account as its Owner."""
        personal = await self.create(OrganizationCreate(name="Pessoal"), personal_of=account_id)
        self._session.add(Membership(organization_id=personal.id, account_id=account_id, role="owner"))
        await self._flush()
        return personal
