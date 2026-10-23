import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import ConflictError
from acervo.core.settings import Settings, Thresholds
from acervo.db.models import Node, PageVersion
from acervo.model_clients.chat_agent import ChatAgent
from acervo.model_clients.fakes import FakeDecider, FakeProbs, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate, AgentUpdate
from acervo.schemas.conversation import Citation, ConversationStart, MessageRead
from acervo.schemas.proposal import ProposalRead
from acervo.services.chat_service import INTERRUPTED, ChatService
from acervo.services.conversation_service import ConversationService, Upload
from acervo.services.events import DONE, InMemoryEventBus, RecordingJobQueue
from acervo.services.file_service import FileService
from acervo.services.proposal_service import ProposalService
from acervo.services.storage import Storage

MakeTree = Callable[..., Awaitable[Any]]
SIMPLE = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}, "Arquivo": None}
FACT = "O prazo de emissão da apólice residencial é de 5 dias úteis."
TO_THE_PAGE: dict[str, FakeProbs] = {
    "descent:": {"Bradesco (pasta) — Contém:\nResidencial": 1.0},
    "descent:Bradesco": {"Residencial (pasta) — Contém:\nEmissão de apólice": 1.0},
    "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 1.0},
    "covered": 0.1,
    "contradicts": 0.1,
    "section": {"Prazos": 1.0},
    "line": {"nenhuma linha": 1.0},
}
# One model response: text, or the tools it calls with their arguments; or what the person does first, then that.
Turn = str | list[tuple[str, dict[str, Any]]] | Callable[[], Awaitable[Any]]


@dataclass
class Script:
    """The chat's model, scripted: each request gets the next turn, and what it was sent is kept."""

    turns: list[Turn] = field(default_factory=list)
    sent: list[list[ModelMessage]] = field(default_factory=list)

    async def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        self.sent.append(messages)
        turn = self.turns.pop(0)
        if callable(turn):
            await turn()
            turn = self.turns.pop(0)
        if isinstance(turn, str):
            for word in turn.split(" "):
                yield f"{word} "
            return
        yield {index: DeltaToolCall(name, json.dumps(args)) for index, (name, args) in enumerate(turn)}

    def returned(self, tool: str) -> Any:
        """What the last call of `tool` gave the model."""
        parts = [
            part
            for messages in self.sent
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == tool
        ]
        return parts[-1].content


@dataclass
class Env:
    uow: UnitOfWork
    session: AsyncSession
    tree: Any
    conversations: ConversationService
    chat: ChatService
    script: Script
    decider: FakeDecider
    bus: InMemoryEventBus
    conversation_id: UUID
    agent_id: UUID

    async def send(self, text: str, *turns: Turn, uploads: list[Upload] | None = None) -> MessageRead:
        self.script.turns += turns
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

    def chunks(self, reply: MessageRead) -> list[dict[str, Any]]:
        """The reply's published stream, `[DONE]` as `{"type": "[DONE]"}`."""
        kept = self.bus.kept[reply.id]
        return [{"type": DONE} if chunk == DONE else json.loads(chunk) for chunk in kept]

    def steps(self) -> list[str]:
        return [
            chunk["toolName"]
            for reply_id in self.bus.kept
            for chunk in map(json.loads, self.bus.kept[reply_id][:-1])
            if chunk["type"] == "tool-input-available"
        ]


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
    script = Script()
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        agent = await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=tree.kb.id, built_in=True)
        await uow.commit()
        bucket, bus, jobs = Storage(storage), InMemoryEventBus(), RecordingJobQueue()
        conversations = ConversationService(uow, bucket, jobs, InMemoryEventBus())
        conversation = await conversations.create(tree.kb.id, ConversationStart())
        model = ChatAgent(FunctionModel(stream_function=script))
        chat = ChatService(uow, bucket, fake_decider, fake_writer, Thresholds(), bus, jobs, model)
        yield Env(uow, session, tree, conversations, chat, script, fake_decider, bus, conversation.id, agent.id)


async def test_a_greeting_gets_text_and_no_tool_call(env: Env) -> None:
    reply = await env.send("oi", "Oi! Em que posso ajudar?")

    assert (reply.status, reply.text, reply.grounded, reply.citations) == (
        "done",
        "Oi! Em que posso ajudar?",
        False,
        [],
    )
    assert env.steps() == []
    deltas = [chunk["delta"] for chunk in env.chunks(reply) if chunk["type"] == "text-delta"]
    assert "".join(deltas).strip() == reply.text and len(deltas) > 1
    assert await env.proposals(reply) == []


async def test_a_question_reads_the_base_and_cites_it(env: Env) -> None:
    page_id = env.tree[PAGE].id

    reply = await env.send(
        "qual o prazo de emissão do residencial?",
        [("list_folder", {})],
        [("read_page", {"node_id": str(page_id), "section": "prazos"})],
        "A apólice sai em cinco dias [1].",
    )

    assert env.script.returned("read_page").cite == "[1]"
    assert env.steps() == ["list_folder", "read_page"]
    assert reply.citations == [
        Citation(
            marker=1, node_id=page_id, kind="page", path="Bradesco/Residencial/Emissão de apólice", anchor="prazos"
        )
    ]
    assert reply.grounded and reply.text == "A apólice sai em cinco dias [1]."
    assert await env.proposals(reply) == []


async def test_a_read_out_of_range_is_told_to_the_model_which_tries_again(env: Env, storage: Settings) -> None:
    with SIMPLE.open("rb") as source:
        pdf = await FileService(env.uow, Storage(storage)).save(env.tree.kb.id, None, "CG 2026.pdf", source)

    reply = await env.send(
        "o que diz a página 10?",
        [("read_pdf_pages", {"node_id": str(pdf.id), "first": 10, "last": 10})],
        [("read_pdf_pages", {"node_id": str(pdf.id), "first": 3, "last": 3})],
        "O PDF tem 3 páginas; a última diz isto [1].",
    )

    retried = [
        part.content
        for message in env.script.sent[1]
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.outcome == "retried"
    ]
    assert retried == ["o PDF tem 3 páginas"]
    assert (reply.status, [c.page for c in reply.citations]) == ("done", [3])


async def test_a_fact_calls_file_fact_and_becomes_an_append_with_its_decisions_logged(env: Env) -> None:
    reply = await env.send(FACT, [("file_fact", {"text": FACT})], "Propus um acréscimo em Prazos.")

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status, proposal.run_id) == ("append", "pending", reply.run_id)
    assert env.script.returned("file_fact").where == "Bradesco/Residencial/Emissão de apólice › Prazos"
    assert reply.grounded and reply.status == "done"
    assert await env.markdown() == TEXT
    assert reply.run_id is not None
    logged = await env.uow.decisions.of_run(reply.run_id)
    assert [d.step for d in logged] == ["descent", "descent", "descent", *["page_check"] * 4]
    assert {d.message_id for d in logged} == {reply.id}
    assert env.chunks(reply)[-1] == {"type": DONE}


async def test_a_contradicting_fact_becomes_a_conflict(env: Env) -> None:
    env.decider.table["contradicts"] = 0.9

    reply = await env.send("O prazo é de 3 dias.", [("file_fact", {"text": "O prazo é de 3 dias."})], "Há conflito.")

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status) == ("conflict", "pending")


async def test_an_auto_agent_applies_but_a_conflict_waits(env: Env) -> None:
    await env.auto()

    filed = await env.send(FACT, [("file_fact", {"text": FACT})], "Propus.")
    env.decider.table["contradicts"] = 0.9
    conflicting = await env.send("O prazo é de 3 dias.", [("file_fact", {"text": "O prazo é de 3 dias."})], "Propus.")

    [applied] = await env.proposals(filed)
    assert (applied.status, applied.accepted_by) == ("applied", "auto")
    assert "- Uma nota" in await env.markdown()
    [waiting] = await env.proposals(conflicting)
    assert (waiting.kind, waiting.status) == ("conflict", "pending")


async def test_an_attached_pdf_is_filed_with_file_attachment(env: Env) -> None:
    env.decider.table.update({"descent:": {"Arquivo (pasta)": 1.0}, "descent:Arquivo": {"salvar aqui": 1.0}})

    with SIMPLE.open("rb") as source:
        upload = Upload(name="Condições Gerais 2026.pdf", mime="application/pdf", source=source)
        reply = await env.send(
            "guarda isso",
            [("file_attachment", {"name": "Condições Gerais 2026.pdf"})],
            "Propus salvar em Arquivo.",
            uploads=[upload],
        )

    [proposal] = await env.proposals(reply)
    assert (proposal.kind, proposal.status, proposal.payload.parent_id) == (  # type: ignore[union-attr]
        "save_pdf",
        "pending",
        env.tree["Arquivo"].id,
    )
    [request] = env.script.sent[0][-1].parts
    assert isinstance(request, UserPromptPart) and "Arquivos anexados: Condições Gerais 2026.pdf" in str(
        request.content
    )
    assert await env.session.scalar(select(Node).where(Node.title == "Condições Gerais 2026.pdf")) is None


async def test_move_x_to_y_becomes_a_move_proposal(env: Env) -> None:
    args = {"node_id": str(env.tree["Bradesco/Residencial"].id), "parent_id": str(env.tree["Arquivo"].id)}

    reply = await env.send("Move Residencial para Arquivo", [("move", args)], "Propus mover.")

    [proposal] = await env.proposals(reply)
    assert proposal.kind == "move" and proposal.status == "pending"
    assert proposal.payload.model_dump(include={"from_path", "to_path"}) == {
        "from_path": "Bradesco/Residencial",
        "to_path": "Arquivo",
    }
    assert env.steps() == ["move"]


async def test_a_tool_error_fails_the_reply_with_nothing_applied(env: Env) -> None:
    await env.auto()

    reply = await env.send(
        FACT,
        [("file_fact", {"text": FACT})],
        [("move", {"node_id": str(uuid4()), "parent_id": None})],
        "Não chega aqui.",
    )

    assert reply.status == "failed" and "not found" in (reply.error or "")
    [dropped] = await env.proposals(reply)
    assert (dropped.status, dropped.reject_reason) == ("rejected", None)
    assert await env.markdown() == TEXT
    *_, proposal, metadata, error, finish, done = env.chunks(reply)
    assert (proposal["type"], proposal["id"], proposal["data"]["status"]) == (
        "data-proposal",
        str(dropped.id),
        "rejected",
    )
    assert metadata["messageMetadata"]["status"] == "failed"
    assert error == {"type": "error", "errorText": reply.error}
    assert (finish["type"], done["type"]) == ("finish", DONE)


async def test_retry_runs_the_message_again(env: Env) -> None:
    failed = await env.send("qual o prazo?", [("move", {"node_id": str(uuid4()), "parent_id": None})])
    env.script.turns.append("Cinco dias.")

    retry = await env.conversations.retry(failed.id)
    message = (await env.uow.messages.of_conversation(env.conversation_id))[0]
    reply = await env.chat.handle(message.id, retry.id)

    assert (reply.status, reply.text, reply.replaces_id) == ("done", "Cinco dias.", failed.id)
    # The failed reply is not history: the model got the question alone, again.
    assert [type(sent) for sent in env.script.sent[-1]] == [ModelRequest]


async def test_a_reply_already_replaced_is_not_retried_again(env: Env) -> None:
    failed = await env.send("qual o prazo?", [("move", {"node_id": str(uuid4()), "parent_id": None})])
    await env.conversations.retry(failed.id)

    with pytest.raises(ConflictError):
        await env.conversations.retry(failed.id)
    assert len(await env.uow.messages.of_conversation(env.conversation_id)) == 3


async def test_a_failing_accept_leaves_the_rest_and_logs_once(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    await env.auto()
    accept, accepts = ProposalService.accept, iter([False, True])

    async def first_fails(service: ProposalService, id: UUID, by: Any = "person") -> ProposalRead:
        if not next(accepts):
            raise RuntimeError("o armazenamento caiu")
        return await accept(service, id, by)

    monkeypatch.setattr(ProposalService, "accept", first_fails)

    reply = await env.send(
        "Duas coisas.",
        [("file_fact", {"text": FACT}), ("file_fact", {"text": "A vistoria é feita em 2 dias."})],
        "Propus duas.",
    )

    assert reply.status == "done"
    first, second = await env.proposals(reply)
    assert (first.status, second.status) == ("pending", "applied")
    assert "não foi aplicada (o armazenamento caiu)" in reply.text
    assert reply.run_id is not None
    logged = await env.uow.decisions.of_run(reply.run_id)
    assert [d.step for d in logged] == (["descent"] * 3 + ["page_check"] * 4) * 2


async def test_a_cancelled_job_marks_the_reply_failed(env: Env) -> None:
    async def card(source: Any) -> Any:
        raise asyncio.CancelledError

    env.chat._filing._writer.card = card  # type: ignore[attr-defined]

    with pytest.raises(asyncio.CancelledError):
        await env.send(FACT, [("file_fact", {"text": FACT})])

    [_, reply] = await env.uow.messages.of_conversation(env.conversation_id)
    assert (reply.status, reply.error) == ("failed", INTERRUPTED)
    assert await env.proposals(reply) == []
    types = [chunk["type"] for chunk in env.chunks(reply)]
    assert (types[0], types[-4:]) == ("start", ["message-metadata", "error", "finish", DONE])
    assert types.count("start") == 1


async def test_a_run_streams_text_tools_proposals_sources_and_finish(env: Env) -> None:
    page_id = env.tree[PAGE].id

    reply = await env.send(
        FACT,
        [("read_page", {"node_id": str(page_id), "section": "prazos"})],
        [("file_fact", {"text": FACT})],
        "Hoje são cinco dias [1]; propus o acréscimo.",
    )

    chunks = env.chunks(reply)
    types = [chunk["type"] for chunk in chunks]
    assert chunks[0] == {"type": "start", "messageId": str(reply.id)}
    assert types[-3:] == ["finish-step", "finish", DONE]
    called = [chunk["toolName"] for chunk in chunks if chunk["type"] == "tool-input-available"]
    assert called == ["read_page", "file_fact"]
    [read, filed] = [chunk["output"] for chunk in chunks if chunk["type"] == "tool-output-available"]
    assert (read["cite"], filed["outcome"]) == ("[1]", "proposed")
    [proposal] = await env.proposals(reply)
    proposed = [chunk for chunk in chunks if chunk["type"] == "data-proposal"]
    assert [(p["id"], p["data"]["status"]) for p in proposed] == [(str(proposal.id), "pending")] * 2
    # The first comes with the tool's result, the second once the run ended.
    assert types.index("data-proposal") < types.index("text-start")
    [source] = [chunk for chunk in chunks if chunk["type"] == "source-document"]
    assert (source["sourceId"], source["mediaType"], source["providerMetadata"]["acervo"]["anchor"]) == (
        "[1]",
        "text/markdown",
        "prazos",
    )
    deltas = "".join(chunk["delta"] for chunk in chunks if chunk["type"] == "text-delta")
    assert deltas.strip() == reply.text
    [metadata] = [
        c["messageMetadata"] for c in chunks if c["type"] == "message-metadata" and "status" in c["messageMetadata"]
    ]
    assert metadata == {
        "status": "done",
        "grounded": True,
        "error": None,
        "replaces_id": None,
        "attachments": [],
        "created_at": None,
    }


async def test_an_auto_approved_proposal_is_sent_again_with_the_same_id(env: Env) -> None:
    await env.auto()

    reply = await env.send(FACT, [("file_fact", {"text": FACT})], "Acrescentei.")

    [applied] = await env.proposals(reply)
    sent = [(c["id"], c["data"]["status"]) for c in env.chunks(reply) if c["type"] == "data-proposal"]
    assert sent == [(str(applied.id), "pending"), (str(applied.id), "applied")]


async def test_finish_sends_each_proposal_as_stored_after_the_person_settled_it(env: Env) -> None:
    async def person_accepts() -> None:
        [proposal] = await env.uow.proposals.listed(env.tree.kb.id)
        await env.chat._proposals.accept(proposal.id)  # type: ignore[attr-defined]

    reply = await env.send(FACT, [("file_fact", {"text": FACT})], person_accepts, "Propus um acréscimo.")

    [proposal] = await env.proposals(reply)
    sent = [(c["id"], c["data"]["status"]) for c in env.chunks(reply) if c["type"] == "data-proposal"]
    assert sent == [(str(proposal.id), "pending"), (str(proposal.id), "applied")]
    assert proposal.accepted_by == "person"


async def test_an_auto_agent_skips_a_proposal_the_person_rejected_during_the_run(env: Env) -> None:
    await env.auto()

    async def person_rejects() -> None:
        [proposal] = await env.uow.proposals.listed(env.tree.kb.id)
        await env.chat._proposals.reject(proposal.id, "wrong_place")  # type: ignore[attr-defined]

    reply = await env.send(FACT, [("file_fact", {"text": FACT})], person_rejects, "Propus um acréscimo.")

    [proposal] = await env.proposals(reply)
    assert (reply.status, proposal.status, proposal.reject_reason) == ("done", "rejected", "wrong_place")
    assert "não foi aplicada" not in reply.text
    assert await env.markdown() == TEXT
    assert [c["data"]["status"] for c in env.chunks(reply) if c["type"] == "data-proposal"][-1] == "rejected"
