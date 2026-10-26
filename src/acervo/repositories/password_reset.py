from datetime import datetime
from uuid import UUID

from sqlalchemy import update

from acervo.db.models.password_reset import PasswordReset
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import PasswordResetCreate, PasswordResetRecord, PasswordResetUpdate


class PasswordResetRepository(
    BaseRepository[PasswordReset, PasswordResetRecord, PasswordResetCreate, PasswordResetUpdate]
):
    orm_model = PasswordReset
    read_schema = PasswordResetRecord

    async def latest(self, account_id: UUID) -> PasswordResetRecord | None:
        query = self._select().where(PasswordReset.account_id == account_id).order_by(PasswordReset.created_at.desc())
        reset = await self._session.scalar(query.limit(1))
        return None if reset is None else self._to_read(reset)

    async def by_token(self, token_hash: str) -> PasswordResetRecord | None:
        """The link with this token, its row locked so two requests with the same link cannot both use it."""
        query = self._select().where(PasswordReset.token_hash == token_hash).with_for_update()
        reset = await self._session.scalar(query)
        return None if reset is None else self._to_read(reset)

    async def use_all(self, account_id: UUID, used_at: datetime) -> None:
        """Marks every unused link of the account used."""
        await self._session.execute(
            update(PasswordReset)
            .where(PasswordReset.account_id == account_id, PasswordReset.used_at.is_(None))
            .values(used_at=used_at)
        )
