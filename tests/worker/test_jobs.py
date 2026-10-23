from collections.abc import AsyncIterator

from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.conversation import ConversationStart
from acervo.schemas.kb import KbCreate
from acervo.services.conversation_service import ConversationService
from acervo.services.events import DONE, InMemoryEventBus, RecordingJobQueue
from acervo.services.storage import Storage
from acervo.worker.jobs import handle_message


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

    async def answer(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        yield "Cinco dias."

    bus = InMemoryEventBus()
    ctx = {
        "session_factory": session_factory,
        "storage": storage,
        "decider": fake_decider,
        "writer": fake_writer,
        "settings": test_settings,
        "events": bus,
        "jobs": jobs,
        "chat": ChatAgent(FunctionModel(stream_function=answer)),
    }

    [(job, kwargs)] = jobs.jobs
    await handle_message(ctx, **kwargs)

    assert (job, kwargs["reply_id"]) == ("handle_message", str(posted.reply.id))
    assert bus.kept[posted.reply.id][-1] == DONE
    async with UnitOfWork(session_factory) as check:
        reply = await check.messages.get(posted.reply.id)
    assert (reply.status, reply.text) == ("done", "Cinco dias.")
