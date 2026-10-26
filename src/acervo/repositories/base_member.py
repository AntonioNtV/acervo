from uuid import UUID

from sqlalchemy import delete, or_, select

from acervo.db.models.base_member import BaseMember
from acervo.db.models.kb import Kb
from acervo.db.models.membership import Membership
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import BaseMemberCreate, BaseMemberRecord, BaseMemberUpdate


class BaseMemberRepository(BaseRepository[BaseMember, BaseMemberRecord, BaseMemberCreate, BaseMemberUpdate]):
    orm_model = BaseMember
    read_schema = BaseMemberRecord

    async def visible_kb_ids(self, account_id: UUID, organization_id: UUID | None = None) -> set[UUID]:
        """Bases, live or trashed, where the account has a role: the rule of `AccessService.base_role` in SQL."""
        added = select(BaseMember.id).where(BaseMember.kb_id == Kb.id, BaseMember.account_id == account_id)
        through_organization = select(Membership.id).where(
            Membership.organization_id == Kb.organization_id,
            Membership.account_id == account_id,
            or_(Membership.role.in_(("owner", "admin")), Kb.general_access != "none"),
        )
        query = select(Kb.id).where(or_(added.exists(), through_organization.exists()))
        if organization_id is not None:
            query = query.where(Kb.organization_id == organization_id)
        return set(await self._session.scalars(query))

    async def of_account(self, account_id: UUID) -> list[BaseMemberRecord]:
        """Every base role the account was given, in one query."""
        return [
            self._to_read(added)
            for added in await self._session.scalars(select(BaseMember).where(BaseMember.account_id == account_id))
        ]

    async def delete_in_organization(self, account_id: UUID, organization_id: UUID) -> None:
        """The account's base roles on every base of the organization."""
        bases = select(Kb.id).where(Kb.organization_id == organization_id)
        await self._session.execute(
            delete(BaseMember).where(BaseMember.account_id == account_id, BaseMember.kb_id.in_(bases))
        )
