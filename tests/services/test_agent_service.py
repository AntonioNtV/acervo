import hashlib
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import AuthError, ConflictError
from acervo.db.models import Agent
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.kb import KbCreate, KbRead
from acervo.services.agent_service import AgentService
from acervo.services.base_service import BaseService


@pytest.fixture
async def agents(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[AgentService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield AgentService(uow)


async def _base(uow: UnitOfWork, name: str = "Seguros · Operação") -> KbRead:
    return await BaseService(uow).create(KbCreate(name=name))


async def test_token_is_shown_once_and_only_its_hash_is_kept(
    agents: AgentService, uow: UnitOfWork, session: AsyncSession
) -> None:
    kb = await _base(uow)
    connected = await agents.create(kb.id, AgentCreate(name="Claude"))

    assert connected.token.startswith("acv_") and len(connected.token) > 40
    assert connected.token_hint == connected.token[-4:]
    stored = await session.scalar(select(Agent).where(Agent.id == connected.id))
    assert stored is not None and stored.token_hash == hashlib.sha256(connected.token.encode()).hexdigest()
    listed = await agents.list(kb.id)
    assert [agent.name for agent in listed] == ["Chat do Acervo", "Claude"]
    assert all(not hasattr(agent, "token") for agent in listed)

    authenticated = await agents.authenticate(connected.token)
    assert authenticated.id == connected.id and authenticated.last_used_at is not None


async def test_revoke_ends_authentication(agents: AgentService, uow: UnitOfWork) -> None:
    kb = await _base(uow)
    connected = await agents.create(kb.id, AgentCreate(name="Claude"))

    revoked = await agents.revoke(connected.id)

    assert revoked.revoked_at is not None
    with pytest.raises(AuthError):
        await agents.authenticate(connected.token)
    with pytest.raises(AuthError):
        await agents.authenticate("acv_unknown")


async def test_built_in_chat_cannot_be_revoked(agents: AgentService, uow: UnitOfWork) -> None:
    kb = await _base(uow)
    chat = (await agents.list(kb.id))[0]

    with pytest.raises(ConflictError):
        await agents.revoke(chat.id)
    assert (await agents.list(kb.id))[0].revoked_at is None


async def test_token_of_another_base_fails(agents: AgentService, uow: UnitOfWork) -> None:
    bradesco, porto = await _base(uow, "Bradesco"), await _base(uow, "Porto")
    connected = await agents.create(bradesco.id, AgentCreate(name="Claude"))

    assert (await agents.authenticate(connected.token, bradesco.id)).kb_id == bradesco.id
    with pytest.raises(AuthError):
        await agents.authenticate(connected.token, porto.id)
