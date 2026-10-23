import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from acervo.core.errors import ConflictError
from acervo.core.settings import Settings
from acervo.db.models import Agent, File, Kb, Node, PageLink, PageVersion, Proposal
from acervo.domain.cards import Placement
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate, AgentMode
from acervo.schemas.kb import KbCreate
from acervo.schemas.page import PageTextPut
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    MovePayload,
    PatchPayload,
    ProposalCreate,
    ProposalPayload,
    ProposalRead,
    RenamePayload,
    ReplacePdfPayload,
    SavePdfPayload,
    StagedFile,
)
from acervo.services.page_service import PageService
from acervo.services.proposal_service import ProposalService
from acervo.services.storage import Storage

MakeTree = Callable[..., Awaitable[Any]]
SIMPLE = Path(__file__).parent.parent / "fixtures" / "pdfs" / "simple.pdf"
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md", "CG 2025.pdf"]}, "Arquivo": None}


@dataclass
class Env:
    uow: UnitOfWork
    proposals: ProposalService
    pages: PageService
    storage: Storage
    session: AsyncSession
    tree: Any
    agent_id: UUID

    def node(self, path: str) -> UUID:
        node_id: UUID = self.tree[path].id
        return node_id

    async def propose(self, payload: ProposalPayload, **extra: Any) -> ProposalRead:
        data = ProposalCreate(kb_id=self.tree.kb.id, agent_id=self.agent_id, payload=payload, **extra)
        return await self.proposals.create(data)

    async def versions(self, node_id: UUID) -> list[PageVersion]:
        query = select(PageVersion).where(PageVersion.node_id == node_id).order_by(PageVersion.created_at)
        return list(await self.session.scalars(query.execution_options(populate_existing=True)))

    async def markdown(self, node_id: UUID) -> str:
        return (await self.pages.read(node_id)).markdown

    async def connect(self, mode: AgentMode) -> None:
        """Proposals from here on are by a connected agent in `mode`."""
        agent = await self.uow.agents.create(AgentCreate(name="Claude", mode=mode), kb_id=self.tree.kb.id)
        await self.uow.commit()
        self.agent_id = agent.id


@pytest.fixture
async def env(uow: UnitOfWork, session: AsyncSession, storage: Settings, make_tree: MakeTree) -> AsyncIterator[Env]:
    tree = await make_tree(TREE)
    version = await session.scalar(select(PageVersion).where(PageVersion.node_id == tree[PAGE].id))
    assert version is not None
    version.markdown = TEXT
    await session.flush()
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        chat = await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=tree.kb.id, built_in=True)
        await uow.commit()
        bucket = Storage(storage)
        yield Env(uow, ProposalService(uow, bucket), PageService(uow), bucket, session, tree, chat.id)


def _append(env: Env, lines: list[str], anchor: str = "documentos") -> PatchPayload:
    page = env.tree[PAGE]
    return PatchPayload(
        kind="append",
        page_id=page.id,
        path=PAGE.removesuffix(".md"),
        base_version_id=page.id,
        anchor=anchor,
        heading=anchor.title(),
        op="append",
        lines=lines,
    )


async def _staged(env: Env) -> StagedFile:
    sha256 = hashlib.sha256(SIMPLE.read_bytes()).hexdigest()
    with SIMPLE.open("rb") as source:
        await env.storage.put(f"staged/{sha256}", source, SIMPLE.stat().st_size)
    return StagedFile(storage_key=f"staged/{sha256}", sha256=sha256, size=SIMPLE.stat().st_size, name="cg.pdf")


async def test_append_writes_a_version_by_the_agent_linked_to_the_proposal(env: Env) -> None:
    proposal = await env.propose(_append(env, ["- CPF"]))
    assert await env.markdown(env.node(PAGE)) == TEXT

    applied = await env.proposals.accept(proposal.id)

    assert (applied.status, applied.accepted_by) == ("applied", "person")
    markdown = await env.markdown(env.node(PAGE))
    assert f"- RG\n- CPF <!-- origem: chat · {proposal.created_at.date()} · proposta {proposal.id.hex[:4]} -->\n" in (
        markdown
    )
    *_, version = await env.versions(env.node(PAGE))
    assert (version.author, version.proposal_id, version.markdown) == ("agent", proposal.id, markdown)


async def test_the_persons_working_text_is_cut_before_the_agents_patch(env: Env) -> None:
    node_id = env.node(PAGE)
    typed = TEXT.replace("- RG", "- RG\n- CNH")
    await env.pages.put_text(node_id, PageTextPut(markdown=typed, revision=0), 300)
    proposal = await env.propose(_append(env, ["- CPF"]))

    await env.proposals.accept(proposal.id)

    assert [(v.author, v.proposal_id) for v in await env.versions(node_id)] == [
        ("user", None),
        ("user", None),
        ("agent", proposal.id),
    ]
    assert (await env.versions(node_id))[1].markdown == typed
    page = await env.pages.read(node_id)
    assert "- RG\n- CNH\n- CPF <!--" in page.markdown
    assert page.revision == 2


async def test_edit_replaces_the_line(env: Env) -> None:
    payload = _append(env, ["Sete dias."], anchor="prazos").model_copy(
        update={"kind": "edit", "op": "replace", "line": "Cinco dias."}
    )

    await env.proposals.accept((await env.propose(payload)).id)

    assert "## Prazos\nSete dias. <!-- origem: chat" in await env.markdown(env.node(PAGE))
    assert "Cinco dias." not in await env.markdown(env.node(PAGE))


async def test_conflict_puts_the_new_text_in_place_of_the_current(env: Env) -> None:
    page = env.tree[PAGE]
    payload = ConflictPayload(
        page_id=page.id,
        path="Bradesco/Residencial/Emissão de apólice",
        base_version_id=page.id,
        anchor="prazos",
        heading="Prazos",
        current="Cinco dias.",
        new="Três dias úteis.",
    )

    await env.proposals.accept((await env.propose(payload)).id)

    assert "## Prazos\nTrês dias úteis. <!-- origem: chat" in await env.markdown(page.id)


async def test_create_page_applies_the_edited_version_by_the_agent(env: Env) -> None:
    folder = env.tree["Bradesco/Residencial"]
    payload = CreatePagePayload(
        parent_id=folder.id, parent_path="Bradesco/Residencial", title="Prazos", markdown="# Prazos\n\nCinco dias.\n"
    )
    proposal = await env.propose(payload)
    await env.proposals.edit(proposal.id, payload.model_copy(update={"title": "Prazos de emissão"}))

    await env.proposals.accept(proposal.id)

    node = await env.session.scalar(select(Node).where(Node.title == "Prazos de emissão"))
    assert node is not None and node.parent_id == folder.id
    [version] = await env.versions(node.id)
    assert (version.author, version.proposal_id) == ("agent", proposal.id)
    assert version.markdown.startswith("# Prazos\n\nCinco dias. <!-- origem: chat")
    assert (await env.proposals.get(proposal.id)).payload == payload


async def test_save_pdf_creates_the_node_from_the_staged_file_in_the_other_place(env: Env) -> None:
    staged = await _staged(env)
    arquivo = Placement(node_id=env.node("Arquivo"), path="Arquivo", landing="here", probability=0.3)
    payload = SavePdfPayload(parent_id=env.node("Bradesco"), parent_path="Bradesco", name="CG 2026.pdf")
    proposal = await env.propose(payload, staged=staged, alternatives=[arquivo])
    assert await env.session.scalar(select(File).where(File.sha256 == staged.sha256)) is None

    await env.proposals.other_place(proposal.id)
    await env.proposals.accept(proposal.id)

    node = await env.session.scalar(select(Node).where(Node.title == "CG 2026.pdf"))
    assert node is not None and node.parent_id == env.node("Arquivo")
    file = await env.session.scalar(select(File).where(File.node_id == node.id))
    assert file is not None and (file.sha256, file.pages) == (staged.sha256, 3)


async def test_a_staged_file_is_deleted_once_no_open_proposal_waits_on_it(env: Env) -> None:
    staged = await _staged(env)
    payload = SavePdfPayload(parent_id=env.node("Bradesco"), parent_path="Bradesco", name="CG 2026.pdf")
    first, second = [await env.propose(payload, staged=staged) for _ in range(2)]

    await env.proposals.accept(first.id)
    async with env.storage.download(staged.storage_key) as path:
        assert path.read_bytes() == SIMPLE.read_bytes()
    await env.proposals.reject(second.id, "already_there")

    with pytest.raises(ClientError):
        async with env.storage.download(staged.storage_key):
            pass


async def test_replace_pdf_adds_a_file_version(env: Env) -> None:
    staged = await _staged(env)
    pdf = env.node("Bradesco/Residencial/CG 2025.pdf")
    payload = ReplacePdfPayload(node_id=pdf, path="Bradesco/Residencial/CG 2025.pdf")

    await env.proposals.accept((await env.propose(payload, staged=staged)).id)

    file = await env.session.scalar(select(File).where(File.node_id == pdf).execution_options(populate_existing=True))
    assert file is not None and file.sha256 == staged.sha256


async def test_move_and_rename_go_through_the_tree(env: Env) -> None:
    folder = env.node("Bradesco/Residencial")
    move = MovePayload(node_id=folder, from_path="Bradesco/Residencial", parent_id=env.node("Arquivo"), to_path="")
    rename = RenamePayload(node_id=folder, path="Arquivo/Residencial", title="Residencial antigo")

    await env.proposals.accept((await env.propose(move)).id)
    await env.proposals.accept((await env.propose(rename)).id)

    node = await env.session.get_one(Node, folder, populate_existing=True)
    assert (node.parent_id, node.title) == (env.node("Arquivo"), "Residencial antigo")


async def test_accept_is_idempotent(env: Env) -> None:
    proposal = await env.propose(_append(env, ["- CPF"]))

    first = await env.proposals.accept(proposal.id)
    second = await env.proposals.accept(proposal.id)

    assert (second.status, second.applied_at) == ("applied", first.applied_at)
    assert len(await env.versions(env.node(PAGE))) == 2


async def test_a_stale_proposal_does_not_apply(env: Env) -> None:
    node_id = env.node(PAGE)
    proposal = await env.propose(_append(env, ["- CPF"]))
    gone = TEXT.replace("## Documentos\n- RG\n\n", "")
    await env.pages.put_text(node_id, PageTextPut(markdown=gone, revision=0), 300)

    stale = await env.proposals.accept(proposal.id)

    assert stale.status == "stale"
    assert await env.markdown(node_id) == gone
    assert all(v.author == "user" for v in await env.versions(node_id))


async def test_reject_keeps_its_reason_and_the_staged_file_out_of_the_base(env: Env) -> None:
    staged = await _staged(env)
    payload = SavePdfPayload(parent_id=env.node("Bradesco"), parent_path="Bradesco", name="CG 2026.pdf")
    proposal = await env.propose(payload, staged=staged)

    rejected = await env.proposals.reject(proposal.id, "not_worth_keeping")

    assert (rejected.status, rejected.reject_reason) == ("rejected", "not_worth_keeping")
    assert await env.session.scalar(select(File).where(File.sha256 == staged.sha256)) is None


async def test_auto_agent_applies_on_create_except_a_conflict_and_an_unplaced_input(env: Env) -> None:
    await env.connect("auto")
    page = env.tree[PAGE]
    conflict = ConflictPayload(
        page_id=page.id,
        path="Bradesco/Residencial/Emissão de apólice",
        base_version_id=page.id,
        anchor="prazos",
        heading="Prazos",
        current="Cinco dias.",
        new="Três dias.",
    )

    applied = await env.propose(_append(env, ["- CPF"]))
    waiting = await env.propose(conflict)
    unplaced = await env.proposals.create(
        ProposalCreate(kb_id=env.tree.kb.id, agent_id=env.agent_id, payload=_append(env, ["- CNH"])), placed=False
    )

    assert (applied.status, applied.accepted_by) == ("applied", "auto")
    assert (waiting.status, unplaced.status) == ("pending", "pending")
    markdown = await env.markdown(page.id)
    assert "- CPF" in markdown and "- CNH" not in markdown and "Cinco dias." in markdown


async def test_undo_restores_the_previous_version(env: Env) -> None:
    node_id = env.node(PAGE)
    applied = await env.proposals.accept((await env.propose(_append(env, ["- CPF"]))).id)

    undo = await env.proposals.undo(applied.id)
    assert (undo.kind, undo.status, undo.undo_of) == ("undo", "pending", applied.id)
    await env.proposals.accept(undo.id)

    assert await env.markdown(node_id) == TEXT
    *_, version = await env.versions(node_id)
    assert (version.author, version.proposal_id) == ("agent", undo.id)


async def test_undo_puts_a_moved_node_back_in_its_place(env: Env) -> None:
    await env.connect("auto")
    folder = env.node("Bradesco/Residencial")
    move = MovePayload(node_id=folder, from_path="Bradesco/Residencial", parent_id=env.node("Arquivo"), to_path="")
    applied = await env.propose(move)

    undo = await env.proposals.undo(applied.id)

    assert undo.status == "applied"
    node = await env.session.get_one(Node, folder, populate_existing=True)
    assert node.parent_id == env.node("Bradesco")


@pytest.fixture
async def committed(test_settings: Settings) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], ProposalRead]]:
    """A pending create_page written by sessions that commit, as parallel requests do; removed after."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with UnitOfWork(sessions) as uow:
        kb = await uow.kbs.create(KbCreate(name="Decisões em paralelo"))
        agent = await uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=kb.id, built_in=True)
        payload = CreatePagePayload(parent_id=None, parent_path="", title="Prazos", markdown="# Prazos\n")
        proposal = await uow.proposals.create(ProposalCreate(kb_id=kb.id, agent_id=agent.id, payload=payload))
        await uow.commit()
    yield sessions, proposal
    async with sessions() as session:
        of_base = select(Node.id).where(Node.kb_id == kb.id)
        await session.execute(delete(PageLink).where(PageLink.from_node_id.in_(of_base)))
        await session.execute(delete(PageVersion).where(PageVersion.node_id.in_(of_base)))
        await session.execute(delete(Proposal).where(Proposal.kb_id == kb.id))
        await session.execute(delete(Node).where(Node.kb_id == kb.id))
        await session.execute(delete(Agent).where(Agent.kb_id == kb.id))
        await session.execute(delete(Kb).where(Kb.id == kb.id))
        await session.commit()
    await engine.dispose()


async def test_a_concurrent_accept_and_reject_settle_it_once(
    committed: tuple[async_sessionmaker[AsyncSession], ProposalRead], test_settings: Settings
) -> None:
    sessions, proposal = committed

    async def settle(accept: bool) -> ProposalRead:
        async with UnitOfWork(sessions) as uow:
            service = ProposalService(uow, Storage(test_settings))
            return await (service.accept(proposal.id) if accept else service.reject(proposal.id, "wrong_place"))

    results = await asyncio.gather(settle(True), settle(False), return_exceptions=True)

    [settled] = [result for result in results if isinstance(result, ProposalRead)]
    assert [type(result) for result in results if not isinstance(result, ProposalRead)] == [ConflictError]
    async with sessions() as session:
        pages = await session.scalar(select(func.count()).where(Node.kb_id == proposal.kb_id))
        stored = await session.get_one(Proposal, proposal.id)
    assert (stored.status, pages) == (settled.status, 1 if settled.status == "applied" else 0)
