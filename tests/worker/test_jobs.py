from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.events import ChatEvent, DoneEvent
from acervo.schemas.kb import KbCreate
from acervo.services.chat_service import NOT_YET
from acervo.services.conversation_service import ConversationService, ConversationStart
from acervo.services.events import InMemoryEventBus, RecordingJobQueue
from acervo.services.storage import Storage
from acervo.worker.jobs import handle_message


class RecordingBus:
    def __init__(self) -> None:
        self.events: list[ChatEvent] = []

    async def publish(self, conversation_id: UUID, event: ChatEvent) -> None:
        self.events.append(event)

    def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        raise NotImplementedError


async def test_handle_message_runs_the_chat_and_publishes_done(
    uow: UnitOfWork,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
    fake_decider: FakeDecider,
    fake_writer: FakeWriter,
) -> None:
    storage, jobs = Storage(test_settings), RecordingJobQueue()
    async with uow:
        kb = await uow.kbs.create(KbCreate(name="Seguros · Operação"))
        await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=kb.id, built_in=True)
        conversations = ConversationService(uow, storage, jobs, InMemoryEventBus())
        conversation = await conversations.create(kb.id, ConversationStart())
        posted = await conversations.post(conversation.id, "Qual o prazo de emissão?", [], None)
    fake_decider.table.update({"intent": [0.9, 0.05, 0.03, 0.02], "two_subjects": 0.1})
    bus = RecordingBus()
    ctx = {
        "session_factory": session_factory,
        "storage": storage,
        "decider": fake_decider,
        "writer": fake_writer,
        "settings": test_settings,
        "events": bus,
        "jobs": jobs,
    }

    [(job, kwargs)] = jobs.jobs
    await handle_message(ctx, **kwargs)

    assert (job, kwargs["reply_id"]) == ("handle_message", str(posted.reply.id))
    assert bus.events[-1] == DoneEvent(message_id=posted.reply.id)
    async with UnitOfWork(session_factory) as check:
        reply = await check.messages.get(posted.reply.id)
    assert (reply.status, reply.text) == ("done", NOT_YET)
