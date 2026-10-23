from uuid import UUID

from sqlalchemy import select

from acervo.db.models.conversation import Conversation
from acervo.repositories.base import BaseRepository
from acervo.schemas.conversation import ConversationCreate, ConversationRead, ConversationUpdate


class ConversationRepository(BaseRepository[Conversation, ConversationRead, ConversationCreate, ConversationUpdate]):
    orm_model = Conversation
    read_schema = ConversationRead

    async def of_agent(self, agent_id: UUID) -> list[ConversationRead]:
        """The agent's conversations, the most recently changed first."""
        query = (
            select(Conversation)
            .where(Conversation.agent_id == agent_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
        return [self._to_read(conversation) for conversation in await self._session.scalars(query)]
