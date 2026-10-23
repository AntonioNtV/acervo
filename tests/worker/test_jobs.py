from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.settings import Settings
from acervo.db.models import Message
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.fakes import FakeDecider, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.conversation import ConversationStart
from acervo.schemas.kb import KbCreate
from acervo.schemas.node import NodeAdd
from acervo.services.chat_service import INTERRUPTED, fail_interrupted
from acervo.services.conversation_service import NOT_STARTED, ConversationService
from acervo.services.events import DONE, InMemoryEventBus, RecordingJobQueue
from acervo.services.page_service import PageService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService
from acervo.worker.jobs import handle_message, index_node, index_pending


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


class DownQueue:
    async def enqueue(self, job: str, **kwargs: Any) -> None:
        raise ConnectionError("Redis caiu")


async def test_a_reply_left_working_is_failed_at_startup_and_when_its_job_is_not_enqueued(
    uow: UnitOfWork,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    storage = Storage(test_settings)
    async with uow:
        kb = await uow.kbs.create(KbCreate(name="Seguros · Operação"))
        await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=kb.id, built_in=True)
        conversations = ConversationService(uow, storage, RecordingJobQueue(), InMemoryEventBus())
        conversation = await conversations.create(kb.id, ConversationStart())
        killed = (await conversations.post(conversation.id, "Qual o prazo?", [], None)).reply
        running = (await conversations.post(conversation.id, "E a vistoria?", [], None)).reply
        timeout = test_settings.job_timeout_seconds
        long_ago = datetime.now(UTC) - timedelta(seconds=timeout + 1)
        await session.execute(update(Message).where(Message.id == killed.id).values(updated_at=long_ago))

        await fail_interrupted(uow, timeout)

        down = ConversationService(uow, storage, DownQueue(), InMemoryEventBus())
        unsent = (await down.post(conversation.id, "E o sinistro?", [], None)).reply
    async with UnitOfWork(session_factory) as check:
        replies = {reply.id: reply for reply in await check.messages.of_conversation(conversation.id)}

    assert (replies[killed.id].status, replies[killed.id].error) == ("failed", INTERRUPTED)
    assert replies[running.id].status == "working"
    assert (unsent.status, replies[unsent.id].status, unsent.error) == ("failed", "failed", NOT_STARTED)


async def test_the_sweep_enqueues_each_build_asked_for_once_and_the_job_builds_it(
    uow: UnitOfWork, session: AsyncSession, session_factory: async_sessionmaker[AsyncSession], test_settings: Settings
) -> None:
    async with uow:
        kb = await uow.kbs.create(KbCreate(name="Seguros · Operação"))
        page = await TreeService(uow).create(kb.id, NodeAdd(kind="page", title="Prazos"), markdown="# Prazos\n")
        version = await PageService(uow).read(page.id)
    jobs = RecordingJobQueue()
    ctx = {"session_factory": session_factory, "storage": Storage(test_settings), "settings": test_settings}

    await index_pending(ctx | {"jobs": jobs})
    [(job, kwargs)] = jobs.jobs
    await index_node(ctx, kwargs["node_id"], kwargs["key"])

    key = str(version.version_id)
    assert (job, kwargs) == ("index_node", {"node_id": str(page.id), "key": key, "_job_id": f"index:{page.id}:{key}"})
    async with UnitOfWork(session_factory) as check:
        assert await check.indexes.states([page.id]) == {page.id: "ready"}
