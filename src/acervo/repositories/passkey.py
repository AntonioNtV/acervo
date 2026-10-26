from uuid import UUID

from acervo.db.models.passkey import Passkey
from acervo.repositories.base import BaseRepository
from acervo.schemas.security import PasskeyCreate, PasskeyRecord, PasskeyUpdate


class PasskeyRepository(BaseRepository[Passkey, PasskeyRecord, PasskeyCreate, PasskeyUpdate]):
    orm_model = Passkey
    read_schema = PasskeyRecord

    async def of_account(self, account_id: UUID, lock: bool = False) -> list[PasskeyRecord]:
        """The account's passkeys, oldest first; with `lock`, their rows locked until the transaction ends."""
        query = self._select().where(Passkey.account_id == account_id).order_by(Passkey.created_at, Passkey.id)
        if lock:
            query = query.with_for_update()
        return [self._to_read(passkey) for passkey in await self._session.scalars(query)]

    async def by_credential(self, credential_id: bytes) -> PasskeyRecord | None:
        """The passkey of this credential, its row locked so two sign-ins cannot both move its counter."""
        query = self._select().where(Passkey.credential_id == credential_id).with_for_update()
        passkey = await self._session.scalar(query)
        return None if passkey is None else self._to_read(passkey)

    async def delete(self, id: UUID) -> None:
        await self._session.delete(await self._get_orm(id))
        await self._flush()
