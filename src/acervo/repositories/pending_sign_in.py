from uuid import UUID

from sqlalchemy import delete

from acervo.db.models.pending_sign_in import PendingSignIn
from acervo.repositories.base import BaseRepository
from acervo.schemas.security import PendingSignInCreate, PendingSignInRecord, PendingSignInUpdate


class PendingSignInRepository(
    BaseRepository[PendingSignIn, PendingSignInRecord, PendingSignInCreate, PendingSignInUpdate]
):
    orm_model = PendingSignIn
    read_schema = PendingSignInRecord

    async def by_token(self, token_hash: str) -> PendingSignInRecord | None:
        """The pending sign-in of this token, its row locked so tries on the same code never race."""
        query = self._select().where(PendingSignIn.token_hash == token_hash).with_for_update()
        pending = await self._session.scalar(query)
        return None if pending is None else self._to_read(pending)

    async def delete(self, token_hash: str) -> None:
        await self._session.execute(delete(PendingSignIn).where(PendingSignIn.token_hash == token_hash))

    async def delete_of_account(self, account_id: UUID) -> None:
        await self._session.execute(delete(PendingSignIn).where(PendingSignIn.account_id == account_id))
