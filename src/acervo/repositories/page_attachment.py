from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from acervo.db.models.page_attachment import PageAttachment
from acervo.repositories.base import BaseRepository
from acervo.schemas.attachment import AttachmentCreate, AttachmentRead


class PageAttachmentRepository(BaseRepository[PageAttachment, AttachmentRead, AttachmentCreate, BaseModel]):
    orm_model = PageAttachment
    read_schema = AttachmentRead

    async def of_page(self, page_id: UUID) -> list[AttachmentRead]:
        query = select(PageAttachment).where(PageAttachment.page_id == page_id).order_by(PageAttachment.name)
        return [self._to_read(attachment) for attachment in await self._session.scalars(query)]
