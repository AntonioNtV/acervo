from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select

from acervo.db.models.message import Message
from acervo.repositories.base import BaseRepository
from acervo.schemas.conversation import MessageCreate, MessageRead, MessageUpdate


class MessageRepository(BaseRepository[Message, MessageRead, MessageCreate, MessageUpdate]):
    orm_model = Message
    read_schema = MessageRead

    async def of_conversation(self, conversation_id: UUID) -> list[MessageRead]:
        """The conversation's messages in the order they were sent."""
        query = (
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id)
        )
        return [self._to_read(message) for message in await self._session.scalars(query)]

    async def update(self, id: UUID, data: MessageUpdate) -> MessageRead:
        message = await self._get_orm(id)
        values = {**dict(data), **data.model_dump(mode="json", include={"citations"})}
        for name in data.model_fields_set:
            setattr(message, name, values[name])
        await self._flush()
        return self._to_read(message)

    def _new(self, data: MessageCreate, extra: Mapping[str, Any]) -> Message:
        return Message(**{**dict(data), **data.model_dump(mode="json", include={"attachments", "context"})}, **extra)
