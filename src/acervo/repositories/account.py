from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased, undefer
from sqlalchemy.orm.interfaces import ORMOption

from acervo.db.models.account import Account
from acervo.db.models.membership import Membership
from acervo.db.models.organization import Organization
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

    async def password_only(self, organization_id: UUID) -> list[AccountRecord]:
        """The organization's members with neither a passkey nor two-step verification."""
        query = (
            self._select()
            .join(Membership, Membership.account_id == Account.id)
            .where(
                Membership.organization_id == organization_id,
                Account.two_factor == "none",
                ~Account.has_passkey,  # type: ignore[attr-defined]
            )
        )
        return [self._to_read(account) for account in await self._session.scalars(query)]

    async def sole_owned(self, account_id: UUID) -> list[UUID]:
        """The teams, not the Pessoal, where the account is the only Owner."""
        other = aliased(Membership)
        others = select(other.id).where(
            other.organization_id == Membership.organization_id, other.role == "owner", other.account_id != account_id
        )
        query = (
            select(Membership.organization_id)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.account_id == account_id,
                Membership.role == "owner",
                Organization.personal_of.is_(None),
                ~others.exists(),
            )
            .order_by(Membership.organization_id)
        )
        return list(await self._session.scalars(query))

    async def delete(self, account_id: UUID) -> None:
        """Removes the account with its sessions, codes, reset links, favorites, follows and memberships."""
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
