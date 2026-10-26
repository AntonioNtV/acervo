from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from acervo.db.models.invite import Invite
from acervo.db.models.kb import Kb
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import InviteRecord, InviteRecordCreate, InviteRecordUpdate, OrgRole


class InviteRepository(BaseRepository[Invite, InviteRecord, InviteRecordCreate, InviteRecordUpdate]):
    orm_model = Invite
    read_schema = InviteRecord

    async def pending(self, organization_id: UUID, kb_id: UUID | None, email: str | None = None) -> list[InviteRecord]:
        """Invites to the organization (`kb_id` None) or to the base, not accepted nor revoked, oldest first; only
        those of `email`, ignoring case, when given."""
        query = self._select().where(
            Invite.organization_id == organization_id,
            Invite.kb_id.is_(None) if kb_id is None else Invite.kb_id == kb_id,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
        if email is not None:
            query = query.where(func.lower(Invite.email) == email.lower())
        return [self._to_read(invite) for invite in await self._session.scalars(query.order_by(Invite.created_at))]

    async def base_name(self, token_hash: str) -> str | None:
        """The name of the base the invite of this token is for, even to an account row-level security hides it
        from."""
        name: str | None = await self._session.scalar(select(func.acervo.invited_base_name(token_hash)))
        return name

    async def by_token(self, token_hash: str) -> InviteRecord | None:
        """The invite of this token, its row locked so two requests with the same link cannot both accept it."""
        invite = await self._session.scalar(self._select().where(Invite.token_hash == token_hash).with_for_update())
        return None if invite is None else self._to_read(invite)

    async def claimable(self, email: str, now: datetime) -> list[InviteRecord]:
        """Live invites of `email`, ignoring case, their rows locked."""
        query = self._select().where(
            func.lower(Invite.email) == email.lower(),
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > now,
        )
        return [self._to_read(invite) for invite in await self._session.scalars(query.with_for_update())]

    async def base_names(self, organization_id: UUID, role: OrgRole) -> list[str]:
        """Live bases of the organization a member with `role` reaches (the rule of `visible_kb_ids`), by name."""
        query = select(Kb.name).where(Kb.organization_id == organization_id, Kb.deleted_at.is_(None))
        if role == "member":
            query = query.where(Kb.general_access != "none")
        return list(await self._session.scalars(query.order_by(Kb.name)))
