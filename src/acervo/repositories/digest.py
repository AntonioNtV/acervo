from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, or_, select, update

from acervo.db.models.account import Account
from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.db.models.page_follow import PageFollow
from acervo.db.models.page_version import PageVersion
from acervo.repositories.base import BaseRepository
from acervo.schemas.digest import DigestAccount, DigestChange


class DigestRepository(BaseRepository[Account, DigestAccount, BaseModel, BaseModel]):
    """What the daily digest reads and marks, across `account`, `page_follow` and `page_version`."""

    orm_model = Account
    read_schema = DigestAccount

    async def due(self, now: datetime) -> list[UUID]:
        """Accounts with the digest on, at 8:xx in their time zone and with no digest yet on their local today."""
        local = func.timezone(Account.timezone, now)
        query = select(Account.id).where(
            Account.notify_followed,
            func.extract("hour", local) == 8,
            or_(Account.digest_sent_on.is_(None), Account.digest_sent_on < func.date(local)),
        )
        return list(await self._session.scalars(query))

    async def claim(self, account_id: UUID, today: date) -> bool:
        """Marks today's digest as sent unless it already was or the digest is off; one statement, so two runs
        at once claim it once."""
        query = (
            update(Account)
            .where(
                Account.id == account_id,
                Account.notify_followed,
                or_(Account.digest_sent_on.is_(None), Account.digest_sent_on < today),
            )
            .values(digest_sent_on=today)
            .returning(Account.id)
        )
        return await self._session.scalar(query) is not None

    async def release(self, account_id: UUID, today: date, previous: date | None) -> None:
        """Undoes `claim` when today's digest did not go out, so a retry sends it."""
        query = (
            update(Account)
            .where(Account.id == account_id, Account.digest_sent_on == today)
            .values(digest_sent_on=previous)
        )
        await self._session.execute(query)

    async def changes(self, account_id: UUID, start: datetime, end: datetime) -> list[DigestChange]:
        """The versions saved in [start, end) on the live pages of live bases the account follows, oldest first.
        Row-level security leaves out the bases the account can no longer read: the caller acts as it."""
        query = (
            select(
                Node.id.label("node_id"),
                Node.title,
                Kb.name.label("base"),
                PageVersion.author_id,
                Account.name.label("author"),
                PageVersion.author_known,
            )
            .select_from(PageFollow)
            .join(Node, Node.id == PageFollow.node_id)
            .join(Kb, Kb.id == Node.kb_id)
            .join(PageVersion, PageVersion.node_id == Node.id)
            .outerjoin(Account, Account.id == PageVersion.author_id)
            .where(
                PageFollow.account_id == account_id,
                Node.kind == "page",
                Node.deleted_at.is_(None),
                Kb.deleted_at.is_(None),
                PageVersion.created_at >= start,
                PageVersion.created_at < end,
            )
            .order_by(Node.title, PageVersion.created_at)
        )
        return [DigestChange.model_validate(row, from_attributes=True) for row in await self._session.execute(query)]
