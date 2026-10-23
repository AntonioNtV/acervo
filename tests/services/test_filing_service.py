from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import DecisionUnavailable
from acervo.core.ids import uuid7
from acervo.core.settings import Settings, Thresholds
from acervo.db.models import Node, PageVersion
from acervo.model_clients.fakes import FakeDecider, FakeProbs, FakeWriter
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.conversation import ConversationStart
from acervo.services.conversation_service import ConversationService, Upload
from acervo.services.events import InMemoryEventBus, RecordingJobQueue
from acervo.services.filing_service import FilingService, Origin
from acervo.services.storage import Storage

MakeTree = Callable[..., Awaitable[Any]]
SIMPLE = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}, "Arquivo": None}
FACT = "O prazo de emissão da apólice residencial é de 5 dias úteis."
# Bradesco and Residencial have children, so they are described before the descent; the rest stays bare.
TO_THE_PAGE: dict[str, FakeProbs] = {
    "descent:": {"Bradesco (pasta) — Descrição": 1.0},
    "descent:Bradesco": {"Residencial (pasta) — Descrição": 1.0},
    "descent:Bradesco/Residencial": {"Emissão de apólice (página)": 1.0},
    "covered": 0.1,
    "contradicts": 0.1,
    "section": {"Prazos": 1.0},
    "line": {"nenhuma linha": 1.0},
}


@dataclass
class Env:
    uow: UnitOfWork
    session: AsyncSession
    tree: Any
    filing: FilingService
    decider: FakeDecider
    writer: FakeWriter
    origin: Origin
    conversations: ConversationService
    conversation_id: Any

    async def markdown(self) -> str:
        version = await self.session.scalar(
            select(PageVersion)
            .where(PageVersion.node_id == self.tree[PAGE].id)
            .order_by(PageVersion.created_at.desc())
            .execution_options(populate_existing=True)
        )
        assert version is not None
        return version.markdown


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
        bucket = Storage(storage)
        conversations = ConversationService(uow, bucket, RecordingJobQueue(), InMemoryEventBus())
        conversation = await conversations.create(tree.kb.id, ConversationStart())
        filing = FilingService(uow, bucket, fake_decider, fake_writer, Thresholds())
        origin = Origin(agent, uuid7(), conversation.id)
        yield Env(uow, session, tree, filing, fake_decider, fake_writer, origin, conversations, conversation.id)


async def test_a_fact_becomes_a_pending_append_with_its_decisions_logged(env: Env) -> None:
    filed = await env.filing.fact(FACT, env.origin)

    proposal = filed.proposal
    assert proposal is not None and filed.placed
    assert (proposal.kind, proposal.status, proposal.run_id) == ("append", "pending", env.origin.run_id)
    assert proposal.payload.model_dump(include={"anchor", "path", "lines"}) == {
        "anchor": "prazos",
        "path": "Bradesco/Residencial/Emissão de apólice",
        "lines": ["- Uma nota"],
    }
    assert await env.markdown() == TEXT
    logged = await env.uow.decisions.of_run(env.origin.run_id)
    assert [d.step for d in logged] == ["descent", "descent", "descent", *["page_check"] * 4]
    described = await env.session.scalar(
        select(Node.description).where(Node.id == env.tree["Bradesco"].id).execution_options(populate_existing=True)
    )
    assert described == "Descrição"


async def test_a_contradicting_fact_becomes_a_conflict(env: Env) -> None:
    env.decider.table["contradicts"] = 0.9

    filed = await env.filing.fact("O prazo de emissão é de 3 dias úteis.", env.origin)

    assert filed.proposal is not None and filed.proposal.kind == "conflict"


async def test_a_fact_already_written_proposes_nothing(env: Env) -> None:
    env.decider.table["covered"] = 0.95

    filed = await env.filing.fact("A emissão leva cinco dias.", env.origin)

    assert filed.proposal is None
    assert filed.written is not None
    assert (filed.written.path, filed.written.heading) == ("Bradesco/Residencial/Emissão de apólice", "Prazos")
    assert await env.uow.proposals.listed(env.tree.kb.id) == []


async def test_an_unplaced_fact_waits_with_the_likeliest_places(env: Env) -> None:
    env.decider.table["descent:Bradesco/Residencial"] = {"Emissão de apólice (página)": 0.5}

    filed = await env.filing.fact("O código 7341 não deve mais ser usado.", env.origin)

    assert filed.proposal is not None and not filed.placed
    assert (filed.proposal.kind, filed.proposal.status) == ("create_page", "pending")
    assert filed.proposal.alternatives is not None
    assert filed.proposal.alternatives[0].path == "Bradesco/Residencial/Emissão de apólice"


async def test_a_pdf_becomes_save_pdf_with_its_staged_file(env: Env) -> None:
    env.decider.table.update({"descent:": {"Arquivo (pasta)": 1.0}, "descent:Arquivo": {"salvar aqui": 1.0}})
    with SIMPLE.open("rb") as source:
        upload = Upload(name="Condições Gerais 2026.pdf", mime="application/pdf", source=source)
        posted = await env.conversations.post(env.conversation_id, "", [upload], None)
    [attachment] = posted.message.attachments

    filed = await env.filing.attachment(attachment, env.origin)

    proposal = filed.proposal
    assert proposal is not None and (proposal.kind, proposal.status) == ("save_pdf", "pending")
    assert proposal.payload.model_dump(include={"parent_id", "name"}) == {
        "parent_id": env.tree["Arquivo"].id,
        "name": "Condições Gerais 2026.pdf",
    }
    assert proposal.staged is not None and proposal.staged.storage_key == attachment.storage_key
    [read] = env.writer.inputs["card"]
    assert "Condições Gerais 2026 - página 1" in read.text and read.file_name == "Condições Gerais 2026.pdf"
    assert await env.session.scalar(select(Node).where(Node.title == "Condições Gerais 2026.pdf")) is None


async def test_a_failure_logs_the_decisions_asked_once_and_stores_no_proposal(env: Env) -> None:
    async def patch(request: Any) -> Any:
        raise DecisionUnavailable("o modelo não respondeu")

    env.writer.patch = patch  # type: ignore[method-assign]

    with pytest.raises(DecisionUnavailable):
        await env.filing.fact(FACT, env.origin)

    assert await env.uow.proposals.listed(env.tree.kb.id) == []
    logged = await env.uow.decisions.of_run(env.origin.run_id)
    assert [d.step for d in logged] == ["descent", "descent", "descent", *["page_check"] * 4]
    assert await env.markdown() == TEXT
