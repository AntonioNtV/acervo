from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import exists, select

from acervo.core.errors import NotFoundError
from acervo.db.models.agent import Agent
from acervo.db.models.conversation import Conversation
from acervo.db.models.proposal import Proposal
from acervo.repositories.base import BaseRepository
from acervo.schemas.proposal import AcceptedBy, ProposalCreate, ProposalRead, ProposalSummary, ProposalUpdate

JSON_FIELDS = {"payload", "edited_payload", "alternatives", "staged"}


class ProposalRepository(BaseRepository[Proposal, ProposalRead, ProposalCreate, ProposalUpdate]):
    orm_model = Proposal
    read_schema = ProposalRead

    async def listed(
        self,
        kb_id: UUID,
        status: Literal["pending", "applied"] = "pending",
        accepted_by: AcceptedBy | None = None,
        since: datetime | None = None,
    ) -> list[ProposalSummary]:
        """The base's proposals in `status`, from any conversation or agent: pending ones newest first, applied ones
        most recently applied first, from `since` on."""
        newest = Proposal.created_at if status == "pending" else Proposal.applied_at
        query = (
            select(Proposal, Agent.name, Conversation.title)
            .join(Agent, Agent.id == Proposal.agent_id)
            .outerjoin(Conversation, Conversation.id == Proposal.conversation_id)
            .where(Proposal.kb_id == kb_id, Proposal.status == status)
            .order_by(newest.desc(), Proposal.id.desc())
        )
        if accepted_by is not None:
            query = query.where(Proposal.accepted_by == accepted_by)
        if since is not None:
            query = query.where(Proposal.applied_at >= since)
        return [
            ProposalSummary(**self._to_read(proposal).model_dump(), agent_name=agent, conversation_title=conversation)
            for proposal, agent, conversation in await self._session.execute(query)
        ]

    async def of_message(self, message_id: UUID) -> list[ProposalRead]:
        """The proposals a reply produced, in the order they were made."""
        query = select(Proposal).where(Proposal.message_id == message_id).order_by(Proposal.created_at, Proposal.id)
        return [self._to_read(proposal) for proposal in await self._session.scalars(query)]

    async def last_applied(self, kb_id: UUID) -> ProposalRead | None:
        """The base's most recently applied proposal an undo can revert: undos themselves are left out."""
        query = (
            select(Proposal)
            .where(Proposal.kb_id == kb_id, Proposal.status == "applied", Proposal.kind != "undo")
            .order_by(Proposal.applied_at.desc(), Proposal.id.desc())
            .limit(1)
        )
        proposal = await self._session.scalar(query)
        return None if proposal is None else self._to_read(proposal)

    async def waits_on(self, storage_key: str) -> bool:
        """Whether a pending or stale proposal still waits on the staged file at `storage_key`."""
        waiting = exists().where(
            Proposal.status.in_(("pending", "stale")), Proposal.staged["storage_key"].astext == storage_key
        )
        return bool(await self._session.scalar(select(waiting)))

    async def locked(self, id: UUID) -> ProposalRead:
        """The proposal as committed, its row held until the transaction ends: two settlements of it run one by one."""
        proposal = await self._session.get(Proposal, id, with_for_update=True, populate_existing=True)
        if proposal is None:
            raise NotFoundError(f"proposal {id} not found", {"id": str(id)})
        return self._to_read(proposal)

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
