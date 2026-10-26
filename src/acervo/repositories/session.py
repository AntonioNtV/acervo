from uuid import UUID

from sqlalchemy import delete

from acervo.db.models.session import Session
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import SessionCreate, SessionRecord, SessionUpdate


class SessionRepository(BaseRepository[Session, SessionRecord, SessionCreate, SessionUpdate]):
    orm_model = Session
    read_schema = SessionRecord

    async def of_account(self, account_id: UUID) -> list[SessionRecord]:
        """The account's sessions, the last used first."""
        query = self._select().where(Session.account_id == account_id).order_by(Session.last_seen_at.desc())
        return [self._to_read(session) for session in await self._session.scalars(query)]

    async def delete(self, id: UUID) -> None:
        await self._session.execute(delete(Session).where(Session.id == id))

    async def delete_by_token(self, token_hash: str) -> None:
        await self._session.execute(delete(Session).where(Session.token_hash == token_hash))

    async def delete_of_account(self, account_id: UUID, *, keep_token_hash: str | None = None) -> None:
        """Every session of the account but the one of `keep_token_hash`."""
        query = delete(Session).where(Session.account_id == account_id)
        if keep_token_hash is not None:
            query = query.where(Session.token_hash != keep_token_hash)
        await self._session.execute(query)
