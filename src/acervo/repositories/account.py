from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func
from sqlalchemy.orm import undefer
from sqlalchemy.orm.interfaces import ORMOption

from acervo.db.models.account import Account
from acervo.repositories.base import BaseRepository
from acervo.schemas.account import AccountCreate, AccountRecord, AccountUpdate


class AccountRepository(BaseRepository[Account, AccountRecord, AccountCreate, AccountUpdate]):
    orm_model = Account
    read_schema = AccountRecord

    def _options(self) -> list[ORMOption]:
        # Any option reloads a row already in the session, so `has_passkey` follows a passkey added since.
        return [undefer(Account.has_passkey)]  # type: ignore[attr-defined]

    async def by_email(self, email: str) -> AccountRecord | None:
        """The account of `email`, ignoring case."""
        account = await self._session.scalar(self._select().where(func.lower(Account.email) == email.lower()))
        return None if account is None else self._to_read(account)

    async def delete(self, account_id: UUID) -> None:
        """Removes the account with its sessions, codes, reset links and favorites."""
        await self._session.execute(delete(Account).where(Account.id == account_id))

    async def free_if_stale(self, email: str, created_before: datetime) -> None:
        """Deletes the account of `email` when it was never confirmed and was created before `created_before`."""
        await self._session.execute(
            delete(Account).where(
                func.lower(Account.email) == email.lower(),
                Account.email_verified_at.is_(None),
                Account.created_at < created_before,
            )
        )
