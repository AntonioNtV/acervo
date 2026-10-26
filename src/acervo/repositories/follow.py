from uuid import UUID

from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models.page_follow import PageFollow


class FollowRepository:
    """The pages each account follows, kept in the `page_follow` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def follow(self, account_id: UUID, node_id: UUID) -> None:
        """Follows the page; following it again changes nothing."""
        query = insert(PageFollow).values(account_id=account_id, node_id=node_id).on_conflict_do_nothing()
        await self._session.execute(query)

    async def unfollow(self, account_id: UUID, node_id: UUID) -> None:
        query = delete(PageFollow).where(PageFollow.account_id == account_id, PageFollow.node_id == node_id)
        await self._session.execute(query)

    async def is_following(self, account_id: UUID, node_id: UUID) -> bool:
        query = exists().where(PageFollow.account_id == account_id, PageFollow.node_id == node_id)
        return bool(await self._session.scalar(select(query)))
