import asyncio
import builtins
import logging
import mimetypes
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID

from acervo.core.errors import ConflictError, NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead
from acervo.schemas.conversation import (
    Attachment,
    ConversationCreate,
    ConversationRead,
    ConversationStart,
    ConversationUpdate,
    MessageContext,
    MessageCreate,
    MessagePosted,
    MessageRead,
    MessageUpdate,
    UiMessage,
    UiMetadata,
    UiPart,
    UiProposalPart,
    UiSourcePart,
    UiTextPart,
)
from acervo.services.events import EventBus, JobQueue
from acervo.services.file_service import read_hash
from acervo.services.storage import Storage

HANDLE_MESSAGE = "handle_message"
TITLE_LENGTH = 80
NOT_STARTED = "a resposta não pôde começar; tente de novo"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Upload:
    """A file sent with a message, as received."""

    name: str | None
    mime: str | None
    source: BinaryIO


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
        await self._live(conversation_id)
        return await self._uow.messages.of_conversation(conversation_id)

    async def delete(self, conversation_id: UUID) -> ConversationRead:
        """Out of the list, its messages no longer served; what it proposed and the decisions logged stay."""
        await self._live(conversation_id)
        if any(message.status == "working" for message in await self._uow.messages.of_conversation(conversation_id)):
            raise ConflictError("a conversa ainda está trabalhando", {"id": str(conversation_id)})
        deleted = await self._uow.conversations.update(
            conversation_id, ConversationUpdate(deleted_at=datetime.now(UTC))
        )
        await self._uow.commit()
        return deleted

    async def post(
        self,
        conversation_id: UUID,
        text: str,
        uploads: Sequence[Upload],
        context: MessageContext | None,
    ) -> MessagePosted:
        """Stores the message with its files staged outside the base, and a working reply whose job is enqueued."""
        conversation = await self._live(conversation_id)
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
        return MessagePosted(message=message, reply=await self._run(message, reply))

    async def retry(self, reply_id: UUID) -> MessageRead:
        """A new reply that runs the message again, once: a reply already replaced is not; the job drops what the
        replaced reply left waiting."""
        replaced = await self._uow.messages.get(reply_id)
        if replaced.role != "acervo" or replaced.status == "working":
            raise ConflictError("só uma resposta terminada pode ser refeita", {"id": str(reply_id)})
        await self._live(replaced.conversation_id)
        thread = await self._uow.messages.of_conversation(replaced.conversation_id)
        if any(message.replaces_id == replaced.id for message in thread):
            raise ConflictError("esta resposta já foi refeita", {"id": str(reply_id)})
        message = _asked(thread, replaced)
        reply = await self._uow.messages.create(
            MessageCreate(
                conversation_id=replaced.conversation_id, role="acervo", status="working", replaces_id=replaced.id
            )
        )
        await self._uow.commit()
        return await self._run(message, reply)

    async def redo(self, proposal_id: UUID) -> MessageRead:
        """A stale proposal's message run again into a new reply, on the newest text; the job drops the stale one."""
        proposal = await self._uow.proposals.get(proposal_id)
        if proposal.status != "stale" or proposal.message_id is None:
            raise ConflictError("só uma proposta desatualizada do chat pode ser refeita", {"id": str(proposal_id)})
        return await self.retry(proposal.message_id)

    async def ui_messages(self, conversation_id: UUID) -> builtins.list[UiMessage]:
        """The thread as the AI SDK's UI messages: a reply's text, its proposals as they stand, its citations."""
        thread = await self.messages(conversation_id)
        return [await self._ui_message(message) for message in thread]

    async def stream(self, reply_id: UUID) -> AsyncIterator[str]:
        """A reply's UI message stream: what was kept of it, then what comes live while it works."""
        reply = await self._uow.messages.get(reply_id)
        if reply.role != "acervo":
            raise NotFoundError(f"reply {reply_id} not found", {"id": str(reply_id)})
        await self._live(reply.conversation_id)
        # A stream may stay open for minutes: it must not hold a database connection meanwhile.
        await self._uow.rollback()
        return self._events.follow(reply_id, reply.status == "working")

    async def _ui_message(self, message: MessageRead) -> UiMessage:
        metadata = UiMetadata(
            status=message.status,
            grounded=message.grounded,
            error=message.error,
            replaces_id=message.replaces_id,
            attachments=message.attachments,
            created_at=message.created_at,
        )
        if message.role == "person":
            return UiMessage(id=message.id, role="user", metadata=metadata, parts=_text(message.text))
        parts: builtins.list[UiPart] = []
        if message.status != "working":
            parts += _text(message.text)
            proposals = await self._uow.proposals.of_message(message.id)
            parts += [UiProposalPart(id=proposal.id, data=proposal) for proposal in proposals]
            parts += [UiSourcePart.of(citation) for citation in message.citations]
        return UiMessage(id=message.id, role="assistant", metadata=metadata, parts=parts)

    async def _run(self, message: MessageRead, reply: MessageRead) -> MessageRead:
        """The reply, failed when its job could not be enqueued: no worker would ever end it."""
        try:
            await self._jobs.enqueue(HANDLE_MESSAGE, message_id=str(message.id), reply_id=str(reply.id))
        except Exception:
            logger.exception("reply %s was not enqueued", reply.id)
            reply = await self._uow.messages.update(reply.id, MessageUpdate(status="failed", error=NOT_STARTED))
            await self._uow.commit()
        return reply

    async def _live(self, conversation_id: UUID) -> ConversationRead:
        conversation = await self._uow.conversations.get(conversation_id)
        if conversation.deleted_at is not None:
            raise NotFoundError(f"conversation {conversation_id} not found", {"id": str(conversation_id)})
        return conversation

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
        max_bytes = self._storage.settings.upload_max_bytes
        sha256, size, _ = await asyncio.to_thread(read_hash, upload.source, max_bytes)
        if size > max_bytes:
            raise ValidationError(too_large(max_bytes), {"max_bytes": max_bytes})
        # Outside the keys of the base's files, so discarding a staged file never touches one saved in the base.
        key = f"staged/{kb_id}/{sha256}"
        await self._storage.put(key, upload.source, size)
        mime = upload.mime or mimetypes.guess_type(upload.name)[0] or "application/octet-stream"
        return Attachment(storage_key=key, sha256=sha256, size=size, name=upload.name, mime=mime)


def too_large(max_bytes: int) -> str:
    return f"o arquivo passa de {max_bytes // (1024 * 1024)} MB"


def _text(text: str) -> list[UiPart]:
    return [UiTextPart(text=text)] if text else []


def _asked(thread: list[MessageRead], reply: MessageRead) -> MessageRead:
    """The person's message a reply answers: the one just before the first reply in its chain of retries."""
    by_id = {message.id: message for message in thread}
    first = reply
    while first.replaces_id is not None:
        first = by_id[first.replaces_id]
    return next(message for message in reversed(thread[: thread.index(first)]) if message.role == "person")
