from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select

from acervo.db.models.page_draft import PageDraft
from acervo.repositories.base import BaseRepository
from acervo.schemas.page import PageDraftCreate, PageDraftRead


class PageDraftRepository(BaseRepository[PageDraft, PageDraftRead, PageDraftCreate, BaseModel]):
    orm_model = PageDraft
    read_schema = PageDraftRead

    async def put(self, data: PageDraftCreate) -> PageDraftRead:
        """The page's single working text, replaced on every save."""
        # The database clock, as versions use: the idle window compares the two.
        now = await self.clock()
        draft = await self._session.scalar(self._select().where(PageDraft.node_id == data.node_id))
        if draft is None:
            return await self.create(data, updated_at=now)
        for name, value in data:
            setattr(draft, name, value)
        draft.updated_at = now
        await self._flush()
        return self._to_read(draft)

    async def clock(self) -> datetime:
        now: datetime = (await self._session.execute(select(func.clock_timestamp()))).scalar_one()
        return now
