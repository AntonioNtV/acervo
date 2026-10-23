from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select

from acervo.db.models.agent import Agent
from acervo.db.models.conversation import Conversation
from acervo.db.models.proposal import Proposal
from acervo.repositories.base import BaseRepository
from acervo.schemas.proposal import ProposalCreate, ProposalRead, ProposalSummary, ProposalUpdate

JSON_FIELDS = {"payload", "edited_payload", "alternatives", "staged"}


class ProposalRepository(BaseRepository[Proposal, ProposalRead, ProposalCreate, ProposalUpdate]):
    orm_model = Proposal
    read_schema = ProposalRead

    async def pending(self, kb_id: UUID) -> list[ProposalSummary]:
        """The base's proposals waiting for the person, from any conversation or agent, newest first."""
        query = (
            select(Proposal, Agent.name, Conversation.title)
            .join(Agent, Agent.id == Proposal.agent_id)
            .outerjoin(Conversation, Conversation.id == Proposal.conversation_id)
            .where(Proposal.kb_id == kb_id, Proposal.status == "pending")
            .order_by(Proposal.created_at.desc(), Proposal.id.desc())
        )
        return [
            ProposalSummary(**self._to_read(proposal).model_dump(), agent_name=agent, conversation_title=conversation)
            for proposal, agent, conversation in await self._session.execute(query)
        ]

    async def update(self, id: UUID, data: ProposalUpdate) -> ProposalRead:
        proposal = await self._get_orm(id)
        values = {**dict(data), **data.model_dump(mode="json", include=JSON_FIELDS)}
        for name in data.model_fields_set:
            setattr(proposal, name, values[name])
        await self._flush()
        return self._to_read(proposal)

    def _new(self, data: ProposalCreate, extra: Mapping[str, Any]) -> Proposal:
        values = {**dict(data), **data.model_dump(mode="json", include=JSON_FIELDS)}
        return Proposal(**values, kind=data.payload.kind, **extra)
