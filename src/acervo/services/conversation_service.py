import asyncio
import builtins
import mimetypes
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.core.errors import ConflictError, NotFoundError, ValidationError
from acervo.domain.cards import Route
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead
from acervo.schemas.conversation import (
    Attachment,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageContext,
    MessageCreate,
    MessageRead,
)
from acervo.schemas.events import ChatEvent, MessageEvent
from acervo.services.events import EventBus, JobQueue
from acervo.services.file_service import read_hash
from acervo.services.storage import Storage

HANDLE_MESSAGE = "handle_message"
TITLE_LENGTH = 80


@dataclass(frozen=True)
class Upload:
    """A file sent with a message, as received."""

    name: str | None
    mime: str | None
    source: BinaryIO


class ConversationStart(BaseModel):
    """A conversation to start in a base."""

    agent_id: UUID | None = Field(default=None, description="The agent it talks to; omitted for the built-in chat.")
    title: str = Field(default="", description="Shown in the list of past conversations.")


class MessagePosted(BaseModel):
    """The person's message, stored, and Acervo's reply, working until its job ends."""

    message: MessageRead
    reply: MessageRead


class Reroute(BaseModel):
    """How a message is to be understood instead ("era uma pergunta")."""

    route: Route = Field(description="The understanding to redo the message with.")


def staged_key(kb_id: UUID, sha256: str) -> str:
    """Outside the keys of the base's files, so discarding a staged file never touches one saved in the base."""
    return f"staged/{kb_id}/{sha256}"


class ConversationService:
    """The conversations of a base and their messages; the work on each message runs in a job."""

    def __init__(self, uow: UnitOfWork, storage: Storage, jobs: JobQueue, events: EventBus) -> None:
        self._uow = uow
        self._storage = storage
        self._jobs = jobs
        self._events = events

    async def list(self, kb_id: UUID, agent_id: UUID | None = None) -> builtins.list[ConversationRead]:
        agent = await self._agent(kb_id, agent_id)
        return await self._uow.conversations.of_agent(agent.id)

    async def create(self, kb_id: UUID, data: ConversationStart) -> ConversationRead:
        agent = await self._agent(kb_id, data.agent_id)
        conversation = await self._uow.conversations.create(
            ConversationCreate(kb_id=kb_id, agent_id=agent.id, title=data.title.strip())
        )
        await self._uow.commit()
        return conversation

    async def messages(self, conversation_id: UUID) -> builtins.list[MessageRead]:
        await self._uow.conversations.get(conversation_id)
        return await self._uow.messages.of_conversation(conversation_id)

    async def post(
        self,
        conversation_id: UUID,
        text: str,
        uploads: Sequence[Upload],
        context: MessageContext | None,
        route: Route | None = None,
    ) -> MessagePosted:
        """Stores the message with its files staged outside the base, and a working reply whose job is enqueued;
        `route`, when given, is how the job must take it (an agent's "remember" is always filed)."""
        conversation = await self._uow.conversations.get(conversation_id)
        text = text.strip()
        if not text and not uploads:
            raise ValidationError("a mensagem está vazia")
        attachments = [await self._stage(conversation.kb_id, upload) for upload in uploads]
        message = await self._uow.messages.create(
            MessageCreate(
                conversation_id=conversation.id, role="person", text=text, attachments=attachments, context=context
            )
        )
        reply = await self._uow.messages.create(
            MessageCreate(conversation_id=conversation.id, role="acervo", status="working")
        )
        change = ConversationUpdate(updated_at=datetime.now(UTC))
        if not conversation.title:
            change.title = (text.splitlines()[0] if text else attachments[0].name)[:TITLE_LENGTH]
        await self._uow.conversations.update(conversation.id, change)
        await self._uow.commit()
        await self._run(conversation.id, message, reply, route, (message, reply))
        return MessagePosted(message=message, reply=reply)

    async def reroute(self, reply_id: UUID, route: Route) -> MessageRead:
        """A new reply that redoes the message as `route`; the job drops what the replaced reply produced."""
        replaced = await self._uow.messages.get(reply_id)
        if replaced.role != "acervo" or replaced.status == "working":
            raise ConflictError("só uma resposta terminada pode ser refeita", {"id": str(reply_id)})
        thread = await self._uow.messages.of_conversation(replaced.conversation_id)
        message = _asked(thread, replaced)
        reply = await self._uow.messages.create(
            MessageCreate(
                conversation_id=replaced.conversation_id, role="acervo", status="working", replaces_id=replaced.id
            )
        )
        await self._uow.commit()
        await self._run(replaced.conversation_id, message, reply, route, (reply,))
        return reply

    async def events(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        await self._uow.conversations.get(conversation_id)
        # A stream may stay open for hours: it must not hold a database connection meanwhile.
        await self._uow.rollback()
        return self._events.subscribe(conversation_id)

    async def _run(
        self,
        conversation_id: UUID,
        message: MessageRead,
        reply: MessageRead,
        route: Route | None,
        new: Sequence[MessageRead],
    ) -> None:
        await self._jobs.enqueue(HANDLE_MESSAGE, message_id=str(message.id), reply_id=str(reply.id), route=route)
        for stored in new:
            await self._events.publish(conversation_id, MessageEvent(message=stored))

    async def _agent(self, kb_id: UUID, agent_id: UUID | None) -> AgentRead:
        await self._uow.kbs.get_in(kb_id)
        if agent_id is None:
            agent = await self._uow.agents.get_by(kb_id=kb_id, built_in=True)
        else:
            agent = await self._uow.agents.get_by(id=agent_id, kb_id=kb_id)
        if agent is None:
            raise NotFoundError(f"agent {agent_id} not found in kb {kb_id}", {"id": str(agent_id)})
        return agent

    async def _stage(self, kb_id: UUID, upload: Upload) -> Attachment:
        if not upload.name:
            raise ValidationError("o arquivo não tem nome")
        sha256, size, _ = await asyncio.to_thread(read_hash, upload.source)
        key = staged_key(kb_id, sha256)
        await self._storage.put(key, upload.source, size)
        mime = upload.mime or mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
        return Attachment(storage_key=key, sha256=sha256, size=size, name=upload.name, mime=mime)


def _asked(thread: list[MessageRead], reply: MessageRead) -> MessageRead:
    """The person's message a reply answers: the one just before the first reply in its chain of redos."""
    by_id = {message.id: message for message in thread}
    first = reply
    while first.replaces_id is not None:
        first = by_id[first.replaces_id]
    return next(message for message in reversed(thread[: thread.index(first)]) if message.role == "person")
