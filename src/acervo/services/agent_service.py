import builtins
import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from acervo.core.errors import AuthError, ConflictError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentConnected, AgentCreate, AgentEdit, AgentRead, AgentUpdate

TOKEN_PREFIX = "acv_"


def _name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("um agente precisa de um nome", {"name": name})
    return name


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AgentService:
    """The agents of a base: the built-in chat and the external agents connected with a token."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def list(self, kb_id: UUID) -> builtins.list[AgentRead]:
        await self._uow.kbs.get_in(kb_id)
        return await self._uow.agents.of_kb(kb_id)

    async def create(self, kb_id: UUID, data: AgentCreate) -> AgentConnected:
        await self._uow.kbs.get_in(kb_id)
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        agent = await self._uow.agents.create(
            AgentCreate(name=_name(data.name), mode=data.mode),
            kb_id=kb_id,
            token_hash=_hash(token),
            token_hint=token[-4:],
        )
        await self._uow.commit()
        return AgentConnected(**agent.model_dump(), token=token)

    async def update(self, agent_id: UUID, data: AgentEdit) -> AgentRead:
        change = AgentUpdate(**data.model_dump(exclude_none=True))
        if data.name is not None:
            change.name = _name(data.name)
        agent = await self._uow.agents.update(agent_id, change)
        await self._uow.commit()
        return agent

    async def revoke(self, agent_id: UUID) -> AgentRead:
        """The token stops working at once; the agent stays, so what it did keeps its name in the history."""
        agent = await self._uow.agents.get(agent_id)
        if agent.built_in:
            raise ConflictError("o chat do Acervo não pode ser revogado", {"id": str(agent_id)})
        if agent.revoked_at is None:
            agent = await self._uow.agents.update(agent_id, AgentUpdate(revoked_at=datetime.now(UTC)))
            await self._uow.commit()
        return agent

    async def authenticate(self, token: str, kb_id: UUID | None = None) -> AgentRead:
        """The live agent holding `token`, and of base `kb_id` when one is given; any other is unauthorized."""
        agent = await self._uow.agents.get_by(token_hash=_hash(token))
        if agent is None or agent.revoked_at is not None or (kb_id is not None and agent.kb_id != kb_id):
            raise AuthError("Invalid or revoked agent token.")
        agent = await self._uow.agents.update(agent.id, AgentUpdate(last_used_at=datetime.now(UTC)))
        await self._uow.commit()
        return agent
