import base64
import io
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import NotFoundError, ValidationError
from acervo.core.settings import Settings
from acervo.db.models import PageVersion
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate, AgentRead
from acervo.schemas.conversation import ConversationStart
from acervo.schemas.proposal import MovePayload, PatchPayload, RenamePayload
from acervo.services.agent_tools import MAX_PDF_PAGES, AgentTools
from acervo.services.conversation_service import ConversationService, Upload
from acervo.services.events import InMemoryEventBus, RecordingJobQueue
from acervo.services.file_service import FileService
from acervo.services.storage import Storage

MakeTree = Callable[..., Awaitable[Any]]
PAGE = "Bradesco/Residencial/Emissão de apólice.md"
TEXT = "# Emissão de apólice\n\n## Documentos\n- RG\n\n## Prazos\nCinco dias.\nÚteis.\n\n## Vistoria\n"
TREE = {"Bradesco": {"Residencial": ["Emissão de apólice.md"]}, "Arquivo": None}


@dataclass
class Env:
    uow: UnitOfWork
    tree: Any
    other: Any
    tools: AgentTools
    agent: AgentRead
    jobs: RecordingJobQueue
    storage: Storage


@pytest.fixture
async def env(uow: UnitOfWork, session: AsyncSession, storage: Settings, make_tree: MakeTree) -> AsyncIterator[Env]:
    tree = await make_tree(TREE)
    other = await make_tree(TREE, name="Outra base")
    version = await session.scalar(select(PageVersion).where(PageVersion.node_id == tree[PAGE].id))
    assert version is not None
    version.markdown = TEXT
    await session.flush()
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        agent = await uow.agents.create(AgentCreate(name="Claude"), kb_id=tree.kb.id, token_hash="x", token_hint="x")
        await uow.commit()
        bucket, jobs = Storage(storage), RecordingJobQueue()
        tools = AgentTools(uow, bucket, jobs, InMemoryEventBus(), agent, wait_seconds=0)
        yield Env(uow, tree, other, tools, agent, jobs, bucket)


def _pdf(directory: Path, pages: int) -> Path:
    path = directory / "long.pdf"
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        for number in range(1, pages + 1):
            document.new_page().insert_text((72, 72), f"Página {number}")
        document.save(path)
    return path


async def test_every_tool_sees_only_its_base(env: Env) -> None:
    page, folder = env.other[PAGE].id, env.other["Bradesco"].id
    calls = [
        env.tools.list_folder(folder),
        env.tools.read_page(page),
        env.tools.read_pdf_pages(page, 1, 1),
        env.tools.edit_section(page, "prazos", "Três dias."),
        env.tools.move(folder, None),
        env.tools.move(env.tree["Arquivo"].id, folder),
        env.tools.rename(folder, "Itaú"),
    ]
    for call in calls:
        with pytest.raises(NotFoundError):
            await call
    assert await env.uow.proposals.listed(env.other.kb.id) == []


async def test_list_folder_gives_each_child_with_kind_and_description(env: Env) -> None:
    root = await env.tools.list_folder()
    assert [(entry.title, entry.kind, entry.child_count) for entry in root.children] == [
        ("Bradesco", "folder", 1),
        ("Arquivo", "folder", 0),
    ]

    inside = await env.tools.list_folder(env.tree["Bradesco/Residencial"].id)
    assert inside.path == "Bradesco/Residencial"
    assert [(entry.title, entry.kind, entry.description) for entry in inside.children] == [
        ("Emissão de apólice", "page", "")
    ]


async def test_read_page_gives_the_whole_page_or_one_section(env: Env) -> None:
    whole = await env.tools.read_page(env.tree[PAGE].id)
    assert (whole.path, whole.markdown, whole.section) == ("Bradesco/Residencial/Emissão de apólice", TEXT, None)
    assert [section.anchor for section in whole.sections] == ["documentos", "prazos", "vistoria"]

    section = await env.tools.read_page(env.tree[PAGE].id, "Prazos")
    assert (section.section, section.markdown) == ("prazos", "## Prazos\nCinco dias.\nÚteis.\n\n")
    with pytest.raises(NotFoundError):
        await env.tools.read_page(env.tree[PAGE].id, "Sinistro")


async def test_read_pdf_pages_caps_the_range(env: Env, tmp_path: Path) -> None:
    with _pdf(tmp_path, MAX_PDF_PAGES + 5).open("rb") as source:
        saved = await FileService(env.uow, env.storage).save(env.tree.kb.id, None, "Tabela.pdf", source)

    read = await env.tools.read_pdf_pages(saved.id, 3, 100)

    assert (read.first, read.last, read.page_count) == (3, 3 + MAX_PDF_PAGES - 1, MAX_PDF_PAGES + 5)
    assert len(read.pages) == MAX_PDF_PAGES and read.pages[0].strip() == "Página 3"
    end = await env.tools.read_pdf_pages(saved.id, MAX_PDF_PAGES + 4, 100)
    assert (end.first, end.last, [text.strip() for text in end.pages]) == (
        MAX_PDF_PAGES + 4,
        MAX_PDF_PAGES + 5,
        [f"Página {MAX_PDF_PAGES + 4}", f"Página {MAX_PDF_PAGES + 5}"],
    )


async def test_writes_are_pending_proposals_of_the_agent(env: Env) -> None:
    page = env.tree[PAGE].id

    edit = await env.tools.edit_section(page, "prazos", "Três dias úteis.")
    empty = await env.tools.edit_section(page, "vistoria", "Dois dias.")
    moved = await env.tools.move(env.tree["Bradesco/Residencial"].id, env.tree["Arquivo"].id)
    renamed = await env.tools.rename(env.tree["Arquivo"].id, "  Arquivo   morto ")

    assert all(p.status == "pending" and p.agent_id == env.agent.id for p in (edit, empty, moved, renamed))
    assert isinstance(edit.payload, PatchPayload) and isinstance(empty.payload, PatchPayload)
    assert (edit.kind, edit.payload.op, edit.payload.line, edit.payload.lines) == (
        "edit",
        "replace",
        "Cinco dias.\nÚteis.",
        ["Três dias úteis."],
    )
    assert (empty.kind, empty.payload.op, empty.payload.line) == ("append", "append", None)
    assert moved.payload == MovePayload(
        node_id=env.tree["Bradesco/Residencial"].id,
        from_path="Bradesco/Residencial",
        from_parent_id=env.tree["Bradesco"].id,
        parent_id=env.tree["Arquivo"].id,
        to_path="Arquivo",
    )
    assert renamed.payload == RenamePayload(node_id=env.tree["Arquivo"].id, path="Arquivo", title="Arquivo morto")
    assert (await env.tools.get_proposal(edit.id)).id == edit.id
    assert (await env.uow.page_versions.current(page)).markdown == TEXT


async def test_get_proposal_of_another_base_is_not_found(env: Env) -> None:
    agent = await env.uow.agents.create(
        AgentCreate(name="Outro"), kb_id=env.other.kb.id, token_hash="y", token_hint="y"
    )
    theirs = AgentTools(env.uow, env.storage, env.jobs, InMemoryEventBus(), agent)
    proposal = await theirs.rename(env.other["Arquivo"].id, "Morto")

    with pytest.raises(NotFoundError):
        await env.tools.get_proposal(proposal.id)


async def test_remember_and_save_file_post_to_the_agents_conversation_and_answer_when_the_wait_ends(
    env: Env,
) -> None:
    filed = await env.tools.remember("O prazo de emissão é de 5 dias úteis.")
    saved = await env.tools.save_file("Tabela.pdf", base64.b64encode(b"%PDF-1.4").decode())

    assert (filed.status, filed.proposals, saved.status) == ("working", [], "working")
    [conversation] = await env.uow.conversations.of_agent(env.agent.id)
    messages = await env.uow.messages.of_conversation(conversation.id)
    assert [(m.role, m.text) for m in messages] == [
        ("person", "O prazo de emissão é de 5 dias úteis."),
        ("acervo", ""),
        ("person", ""),
        ("acervo", ""),
    ]
    assert messages[2].attachments[0].name == "Tabela.pdf"
    assert [(job, kwargs["reply_id"]) for job, kwargs in env.jobs.jobs] == [
        ("handle_message", str(filed.reply_id)),
        ("handle_message", str(saved.reply_id)),
    ]
    assert (await env.tools.get_reply(filed.reply_id)).status == "working"


async def test_save_file_refuses_anything_but_a_pdf(env: Env) -> None:
    with pytest.raises(ValidationError):
        await env.tools.save_file("Notas.txt", base64.b64encode(b"texto").decode())

    assert await env.uow.conversations.of_agent(env.agent.id) == []


async def test_a_file_past_the_cap_is_refused_in_the_chat_and_in_base64(env: Env, storage: Settings) -> None:
    small = Storage(storage.model_copy(update={"upload_max_bytes": 4}))
    tools = AgentTools(env.uow, small, env.jobs, InMemoryEventBus(), env.agent, wait_seconds=0)
    conversations = ConversationService(env.uow, small, env.jobs, InMemoryEventBus())
    conversation = await conversations.create(env.tree.kb.id, ConversationStart(agent_id=env.agent.id))

    with pytest.raises(ValidationError):
        await tools.save_file("Tabela.pdf", base64.b64encode(b"%PDF-1.4").decode())
    with pytest.raises(ValidationError):
        upload = Upload(name="Tabela.pdf", mime="application/pdf", source=io.BytesIO(b"%PDF-1.4"))
        await conversations.post(conversation.id, "", [upload], None)

    assert await env.uow.messages.of_conversation(conversation.id) == []
