from uuid import UUID

from sqlalchemy import select

from acervo.db.models.agent import Agent
from acervo.repositories.base import BaseRepository
from acervo.schemas.agent import AgentCreate, AgentRead, AgentUpdate


class AgentRepository(BaseRepository[Agent, AgentRead, AgentCreate, AgentUpdate]):
    orm_model = Agent
    read_schema = AgentRead

    async def of_kb(self, kb_id: UUID) -> list[AgentRead]:
        """The base's agents: its built-in chat first, then the others as they were connected."""
        query = select(Agent).where(Agent.kb_id == kb_id).order_by(Agent.built_in.desc(), Agent.created_at, Agent.id)
        return [self._to_read(agent) for agent in await self._session.scalars(query)]
