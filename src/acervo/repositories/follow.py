from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from acervo.db.models.page_follow import PageFollow
from acervo.repositories.base import BaseRepository
from acervo.schemas.follow import FollowCreate, FollowRead


class FollowRepository(BaseRepository[PageFollow, FollowRead, FollowCreate, BaseModel]):
    """The pages each account follows, kept in the `page_follow` table."""

    orm_model = PageFollow
    read_schema = FollowRead

    async def follow(self, data: FollowCreate) -> None:
        """Follows the page; following it again changes nothing."""
        await self._session.execute(insert(PageFollow).values(**data.model_dump()).on_conflict_do_nothing())

    async def unfollow(self, data: FollowCreate) -> None:
        query = delete(PageFollow).where(PageFollow.account_id == data.account_id, PageFollow.node_id == data.node_id)
        await self._session.execute(query)
