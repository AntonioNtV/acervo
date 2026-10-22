from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete

from acervo.db.models.page_draft import PageDraft
from acervo.repositories.base import BaseRepository
from acervo.schemas.page import PageDraftCreate, PageDraftRead


class PageDraftRepository(BaseRepository[PageDraft, PageDraftRead, PageDraftCreate, BaseModel]):
    orm_model = PageDraft
    read_schema = PageDraftRead

    async def put(self, data: PageDraftCreate) -> PageDraftRead:
        """The page's single draft, replaced on every autosave."""
        draft = await self._session.scalar(self._select().where(PageDraft.node_id == data.node_id))
        if draft is None:
            return await self.create(data)
        draft.markdown, draft.base_version_id = data.markdown, data.base_version_id
        await self._flush()
        return self._to_read(draft)

    async def discard(self, node_id: UUID) -> None:
        await self._session.execute(delete(PageDraft).where(PageDraft.node_id == node_id))
