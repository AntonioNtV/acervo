from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import DecisionUnavailable
from acervo.core.settings import Settings, Thresholds
from acervo.db.models import Node, PageVersion
from acervo.domain.cards import Route, WrittenPatch
from acervo.model_clients.fakes import FakeDecider, FakeProbs, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate, AgentUpdate
from acervo.schemas.conversation import MessageRead
from acervo.schemas.events import ChatEvent, DoneEvent, ErrorEvent
from acervo.schemas.proposal import ProposalRead
from acervo.services.chat_service import NOT_YET, ChatService
from acervo.services.conversation_service import ConversationService, ConversationStart, Upload
from acervo.services.events import InMemoryEventBus, RecordingJobQueue
from acervo.services.storage import Storage

MakeTree = Callable[..., Awaitable[Any]]
SIMPLE = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}, "Arquivo": None}
GUARDAR = [0.05, 0.9, 0.03, 0.02]
# Bradesco and Residencial have children, so the chat describes them before the descent; the rest stays bare.
TO_THE_PAGE: dict[str, FakeProbs] = {
    "intent": GUARDAR,
    "two_subjects": 0.1,
    "descent:": {"Bradesco (pasta) — Descrição": 1.0},
    "descent:Bradesco": {"Residencial (pasta) — Descrição": 1.0},
    "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 1.0},
    "covered": 0.1,
    "contradicts": 0.1,
    "section": {"Prazos": 1.0},
    "line": {"nenhuma linha": 1.0},
}


@dataclass
class RecordingBus:
    events: list[ChatEvent] = field(default_factory=list)

    async def publish(self, conversation_id: UUID, event: ChatEvent) -> None:
        self.events.append(event)

    def subscribe(self, conversation_id: UUID) -> AsyncIterator[ChatEvent]:
        raise NotImplementedError


@dataclass
class Env:
    uow: UnitOfWork
    session: AsyncSession
    tree: Any
    conversations: ConversationService
    chat: ChatService
    decider: FakeDecider
    writer: FakeWriter
    bus: RecordingBus
    jobs: RecordingJobQueue
    conversation_id: UUID
    agent_id: UUID

    async def send(self, text: str, uploads: list[Upload] | None = None) -> MessageRead:
        posted = await self.conversations.post(self.conversation_id, text, uploads or [], None)
        return await self.chat.handle(posted.message.id, posted.reply.id)

    async def proposals(self, reply: MessageRead) -> list[ProposalRead]:
        return await self.uow.proposals.of_message(reply.id)

    async def markdown(self) -> str:
        version = await self.session.scalar(
            select(PageVersion)
            .where(PageVersion.node_id == self.tree[PAGE].id)
            .order_by(PageVersion.created_at.desc())
            .execution_options(populate_existing=True)
        )
        assert version is not None
        return version.markdown

    async def auto(self) -> None:
        await self.uow.agents.update(self.agent_id, AgentUpdate(mode="auto"))
        await self.uow.commit()


@pytest.fixture
async def env(
    uow: UnitOfWork,
    session: AsyncSession,
    storage: Settings,
    make_tree: MakeTree,
    fake_decider: FakeDecider,
    fake_writer: FakeWriter,
) -> AsyncIterator[Env]:
    tree = await make_tree(TREE)
    version = await session.scalar(select(PageVersion).where(PageVersion.node_id == tree[PAGE].id))
    assert version is not None
    version.markdown = TEXT
    await session.flush()
    fake_decider.table.update(TO_THE_PAGE)
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        agent = await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=tree.kb.id, built_in=True)
        await uow.commit()
        bucket, bus, jobs = Storage(storage), RecordingBus(), RecordingJobQueue()
        conversations = ConversationService(uow, bucket, jobs, InMemoryEventBus())
        conversation = await conversations.create(tree.kb.id, ConversationStart())
        chat = ChatService(uow, bucket, fake_decider, fake_writer, Thresholds(), bus, jobs)
        yield Env(
            uow, session, tree, conversations, chat, fake_decider, fake_writer, bus, jobs, conversation.id, agent.id
        )


async def test_a_fact_becomes_an_append_with_its_decisions_logged(env: Env) -> None:
    reply = await env.send("O prazo de emissão da apólice residencial é de 5 dias úteis.")

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status, proposal.run_id) == ("append", "pending", reply.run_id)
    assert proposal.payload.model_dump(include={"anchor", "path", "lines"}) == {
        "anchor": "prazos",
        "path": "Bradesco/Residencial/Emissão de apólice",
        "lines": ["- Uma nota"],
    }
    assert (reply.status, reply.understood_as) == ("done", "guardar")
    assert "Acréscimo: Bradesco/Residencial/Emissão de apólice › Prazos" in reply.text
    assert await env.markdown() == TEXT
    assert reply.run_id is not None
    logged = await env.uow.decisions.of_run(reply.run_id)
    assert [d.step for d in logged] == ["route", "route", "descent", "descent", "descent", *["page_check"] * 4]
    assert {d.message_id for d in logged} == {reply.id}
    assert isinstance(env.bus.events[-1], DoneEvent)
    described = await env.session.scalar(
        select(Node.description).where(Node.id == env.tree["Bradesco"].id).execution_options(populate_existing=True)
    )
    assert described == "Descrição"


async def test_a_contradicting_fact_becomes_a_conflict(env: Env) -> None:
    env.decider.table["contradicts"] = 0.9

    reply = await env.send("O prazo de emissão é de 3 dias úteis.")

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status) == ("conflict", "pending")


async def test_an_ambiguous_message_asks_first_and_proposes_nothing(env: Env) -> None:
    env.decider.table["intent"] = [0.4, 0.35, 0.15, 0.1]

    reply = await env.send("apólice residencial")

    assert await env.proposals(reply) == []
    assert (reply.text, reply.understood_as) == ("Procurar a resposta ou guardar isso na base?", None)


async def test_two_subjects_give_two_results_in_one_reply(env: Env) -> None:
    env.decider.table["two_subjects"] = 0.9
    env.writer.split_output = ["O prazo é de 5 dias.", "Pergunta: qual o prazo do auto?"]
    intents = iter([GUARDAR, GUARDAR, [0.9, 0.05, 0.03, 0.02]])
    ask = env.decider.ask

    async def ask_in_turn(state: str, questions: Any) -> Any:
        if questions[0].id == "intent":
            env.decider.table["intent"] = next(intents)
        return await ask(state, questions)

    env.decider.ask = ask_in_turn  # type: ignore[method-assign]

    reply = await env.send("O prazo é de 5 dias. E qual o prazo do auto?")

    [proposal] = await env.proposals(reply)
    assert proposal.kind == "append"
    assert reply.text.splitlines()[1] == NOT_YET
    assert reply.understood_as == "guardar"


async def test_a_pdf_becomes_save_pdf_with_its_staged_file(env: Env) -> None:
    env.decider.table.update({"descent:": {"Arquivo (pasta)": 1.0}, "descent:Arquivo": {"salvar aqui": 1.0}})

    with SIMPLE.open("rb") as source:
        reply = await env.send("", [Upload(name="Condições Gerais 2026.pdf", mime="application/pdf", source=source)])

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status) == ("save_pdf", "pending")
    assert proposal.payload.model_dump(include={"parent_id", "name"}) == {
        "parent_id": env.tree["Arquivo"].id,
        "name": "Condições Gerais 2026.pdf",
    }
    message = (await env.uow.messages.of_conversation(env.conversation_id))[0]
    assert proposal.staged is not None and proposal.staged.storage_key == message.attachments[0].storage_key
    [read] = env.writer.inputs["card"]
    assert "Condições Gerais 2026 - página 1" in read.text and read.file_name == "Condições Gerais 2026.pdf"
    assert await env.session.scalar(select(Node).where(Node.title == "Condições Gerais 2026.pdf")) is None


async def test_a_question_gets_the_next_phase_reply(env: Env) -> None:
    env.decider.table["intent"] = [0.9, 0.05, 0.03, 0.02]

    reply = await env.send("Qual o prazo de emissão?")

    assert (reply.text, reply.understood_as) == (NOT_YET, "perguntar")
    assert await env.proposals(reply) == []


async def test_reroute_drops_the_replaced_replys_pending_proposal(env: Env) -> None:
    first = await env.send("O prazo é de 5 dias.")
    [dropped] = await env.proposals(first)
    route: Route = "perguntar"

    redo = await env.conversations.reroute(first.id, route)
    message = (await env.uow.messages.of_conversation(env.conversation_id))[0]
    reply = await env.chat.handle(message.id, redo.id, route)

    assert (reply.text, reply.understood_as, reply.replaces_id) == (NOT_YET, "perguntar", first.id)
    rejected = await env.uow.proposals.get(dropped.id)
    assert (rejected.status, rejected.reject_reason) == ("rejected", None)


async def test_an_auto_agent_applies_but_a_conflict_waits(env: Env) -> None:
    await env.auto()

    applied = await env.send("O prazo é de 5 dias.")
    env.decider.table["contradicts"] = 0.9
    waiting = await env.send("O prazo é de 3 dias.")

    [append] = await env.proposals(applied)
    assert (append.status, append.accepted_by) == ("applied", "auto")
    assert "- Uma nota <!-- origem: chat" in await env.markdown()
    assert [p.status for p in await env.proposals(waiting)] == ["pending"]


async def test_a_failure_leaves_nothing_applied(env: Env) -> None:
    await env.auto()
    env.decider.table["two_subjects"] = 0.9
    env.writer.split_output = ["O prazo é de 5 dias.", "O prazo do auto é de 2 dias."]
    written = iter([WrittenPatch(lines=["- 5 dias"])])

    async def patch(request: Any) -> WrittenPatch:
        try:
            return next(written)
        except StopIteration:
            raise DecisionUnavailable("o modelo não respondeu") from None

    env.writer.patch = patch  # type: ignore[method-assign]

    reply = await env.send("O prazo é de 5 dias. O prazo do auto é de 2 dias.")

    assert (reply.status, reply.error) == ("failed", "o modelo não respondeu")
    assert await env.proposals(reply) == []
    assert await env.markdown() == TEXT
    error = env.bus.events[-1]
    assert isinstance(error, ErrorEvent) and error.error == "decision_unavailable"
