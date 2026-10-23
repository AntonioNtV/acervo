"""What an agent connected with a token can do in its base: the MCP server's tools, on the services the chat uses.
Reads read; every write is a proposal through `ProposalService`, applied there only for an agent in auto mode."""

import asyncio
import base64
import binascii
import io
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.core.errors import NotFoundError, ValidationError
from acervo.domain.patch import span
from acervo.domain.sections import sections
from acervo.pipeline.pdf import reader
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead
from acervo.schemas.conversation import MessageRead, MessageStatus
from acervo.schemas.node import NodeKind, NodeRead
from acervo.schemas.page import Section
from acervo.schemas.proposal import (
    MovePayload,
    PatchPayload,
    ProposalCreate,
    ProposalPayload,
    ProposalRead,
    RenamePayload,
)
from acervo.services.agent_service import AgentService
from acervo.services.conversation_service import ConversationService, ConversationStart, Upload
from acervo.services.events import EventBus, JobQueue
from acervo.services.page_service import PageService
from acervo.services.proposal_service import ProposalService, enqueue_refresh
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

# The most pages of a PDF one call reads: an agent moves through a large PDF a range at a time, never all of it.
MAX_PDF_PAGES = 10
# How long `remember` and `save_file` wait for their message's job before answering with what it has so far.
WAIT_SECONDS = 60.0
POLL_SECONDS = 0.5


class Entry(BaseModel):
    """A node right under a folder or page."""

    id: UUID = Field(description="Node ID.")
    kind: NodeKind = Field(description="folder, page or file.")
    title: str = Field(description="Title; a file's keeps its extension.")
    description: str = Field(description="What it holds.")
    child_count: int = Field(description="How many nodes are right under it.")
    pages: int | None = Field(description="A PDF's page count; null for anything else.")


class Folder(BaseModel):
    """What is right under a folder or page, or under the base's root."""

    node_id: UUID | None = Field(description="The folder or page; null for the root.")
    path: str = Field(description="Its path, joined by /; empty for the root.")
    children: list[Entry] = Field(description="In the order the base shows them.")


class PageContent(BaseModel):
    """A page's text as the person last typed it, whole or one section."""

    node_id: UUID = Field(description="The page.")
    path: str = Field(description="Its path, joined by /.")
    version_id: UUID = Field(description="The version the text is.")
    section: str | None = Field(description="The anchor of the section read; null for the whole page.")
    markdown: str = Field(description="The text.")
    sections: list[Section] = Field(description="Every `##` section of the page, in order.")


class PdfPages(BaseModel):
    """The text of some pages of a PDF, read from the original file."""

    node_id: UUID = Field(description="The file.")
    path: str = Field(description="Its path, joined by /.")
    first: int = Field(description="The first page read, counted from 1.")
    last: int = Field(description="The last page read; at most MAX_PDF_PAGES after `first`.")
    page_count: int = Field(description="How many pages the PDF has.")
    pages: list[str] = Field(description="Each page's text, from `first` to `last`.")


class Filed(BaseModel):
    """What a message of the agent produced: Acervo's reply and its proposals."""

    reply_id: UUID = Field(description="Acervo's reply in the agent's conversation.")
    status: MessageStatus = Field(description="working when the wait ended before the job did; done or failed.")
    reply: str = Field(description="Acervo's reply.")
    error: str | None = Field(description="Why it failed; null unless failed.")
    run_id: UUID | None = Field(description="The run that handles it, to find its decisions.")
    proposals: list[ProposalRead] = Field(description="Each pending, or applied for an agent in auto mode.")


async def authenticate(session_factory: async_sessionmaker[AsyncSession], token: str) -> AgentRead:
    """The live agent holding `token`; any other token is unauthorized."""
    async with UnitOfWork(session_factory) as uow:
        return await AgentService(uow).authenticate(token)


@asynccontextmanager
async def open_tools(
    agent: AgentRead,
    session_factory: async_sessionmaker[AsyncSession],
    storage: Storage,
    jobs: JobQueue,
    events: EventBus,
) -> AsyncIterator["AgentTools"]:
    async with UnitOfWork(session_factory) as uow:
        yield AgentTools(uow, storage, jobs, events, agent)


class AgentTools:
    """The tools of one agent, each scoped to its base: a node of another base is not found."""

    def __init__(
        self,
        uow: UnitOfWork,
        storage: Storage,
        jobs: JobQueue,
        events: EventBus,
        agent: AgentRead,
        wait_seconds: float = WAIT_SECONDS,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._jobs = jobs
        self._agent = agent
        self._wait_seconds = wait_seconds
        self._pages = PageService(uow)
        self._tree = TreeService(uow)
        self._proposals = ProposalService(uow, storage)
        self._conversations = ConversationService(uow, storage, jobs, events)

    async def list_folder(self, node_id: UUID | None = None) -> Folder:
        path = ""
        if node_id is not None:
            node = await self._node(node_id)
            if node.kind == "file":
                raise ValidationError("um arquivo não tem nada dentro", {"id": str(node_id)})
            path = await self._uow.nodes.path(node.id)
        children = await self._tree.children(self._agent.kb_id, node_id)
        entries = [Entry(**child.model_dump(include=set(Entry.model_fields))) for child in children]
        return Folder(node_id=node_id, path=path, children=entries)

    async def read_page(self, node_id: UUID, section: str | None = None) -> PageContent:
        """`section` is an anchor or a heading of the page."""
        node = await self._node(node_id, "page")
        # What the agent reads is what the person typed.
        await self._pages.cut(node.id)
        page = await self._pages.read(node.id)
        markdown, anchor = page.markdown, None
        if section is not None:
            found, start, end = _section(page.markdown, section)
            markdown, anchor = "\n".join(page.markdown.splitlines()[start:end]) + "\n", found.anchor
        return PageContent(
            node_id=node.id,
            path=await self._uow.nodes.path(node.id),
            version_id=page.version_id,
            section=anchor,
            markdown=markdown,
            sections=page.sections,
        )

    async def read_pdf_pages(self, node_id: UUID, first: int, last: int) -> PdfPages:
        """Pages `first` to `last`, counted from 1; at most MAX_PDF_PAGES of them."""
        node = await self._node(node_id, "file")
        if first < 1 or last < first:
            raise ValidationError("as páginas vão de 1 em diante, a primeira antes da última", {"first": first})
        content = await self._uow.files.of_node(node.id)
        if content.mime != "application/pdf":
            raise ValidationError("o arquivo não é um PDF", {"id": str(node_id)})
        if content.protected:
            raise ValidationError("o PDF pede senha para abrir", {"id": str(node_id)})
        path = await self._uow.nodes.path(node.id)
        # The bytes come from the bucket; the database is not held meanwhile.
        await self._uow.rollback()
        async with self._storage.download(content.storage_key) as local:
            texts, page_count = await asyncio.to_thread(
                reader.page_text, local, first, first + min(last - first, MAX_PDF_PAGES - 1)
            )
        if not texts:
            raise ValidationError(f"o PDF tem {page_count} páginas", {"page_count": page_count})
        return PdfPages(
            node_id=node.id, path=path, first=first, last=first + len(texts) - 1, page_count=page_count, pages=texts
        )

    async def remember(self, text: str) -> Filed:
        """A fact, filed as the chat files one, in a conversation of the agent."""
        return await self._file(text, [])

    async def save_file(self, name: str, content_base64: str) -> Filed:
        """A PDF, filed as one dropped in the chat is."""
        try:
            data = base64.b64decode(content_base64, validate=True)
        except binascii.Error as exc:
            raise ValidationError("o conteúdo não está em base64", {"name": name}) from exc
        upload = Upload(name=name, mime=mimetypes.guess_type(name)[0], source=io.BytesIO(data))
        return await self._file("", [upload])

    async def edit_section(self, node_id: UUID, section: str, new_text: str) -> ProposalRead:
        """The section's text under its heading becomes `new_text`."""
        node = await self._node(node_id, "page")
        await self._pages.cut(node.id)
        page = await self._pages.read(node.id)
        found, start, end = _section(page.markdown, section)
        body = page.markdown.splitlines()[start + 1 : end]
        while body and not body[-1].strip():
            body.pop()
        while body and not body[0].strip():
            body.pop(0)
        payload = PatchPayload(
            kind="edit" if body else "append",
            page_id=node.id,
            path=await self._uow.nodes.path(node.id),
            base_version_id=page.version_id,
            anchor=found.anchor,
            heading=found.heading,
            op="replace" if body else "append",
            line="\n".join(body) if body else None,
            lines=new_text.strip("\n").splitlines(),
        )
        return await self._propose(payload)

    async def move(self, node_id: UUID, parent_id: UUID | None) -> ProposalRead:
        """`parent_id` null moves it to the base's root."""
        node = await self._node(node_id)
        to_path = ""
        if parent_id is not None:
            parent = await self._node(parent_id)
            if parent.kind == "file":
                raise ValidationError("nada vai dentro de um arquivo", {"parent_id": str(parent_id)})
            to_path = await self._uow.nodes.path(parent.id)
        from_path = await self._uow.nodes.path(node.id)
        return await self._propose(
            MovePayload(node_id=node.id, from_path=from_path, parent_id=parent_id, to_path=to_path)
        )

    async def rename(self, node_id: UUID, title: str) -> ProposalRead:
        node = await self._node(node_id)
        title = " ".join(title.split())
        if not title:
            raise ValidationError("um título não pode ser vazio", {"title": title})
        path = await self._uow.nodes.path(node.id)
        return await self._propose(RenamePayload(node_id=node.id, path=path, title=title))

    async def get_proposal(self, proposal_id: UUID) -> ProposalRead:
        proposal = await self._proposals.get(proposal_id)
        if proposal.kb_id != self._agent.kb_id:
            raise NotFoundError(f"proposal {proposal_id} not found", {"id": str(proposal_id)})
        return proposal

    async def _node(self, node_id: UUID, kind: NodeKind | None = None) -> NodeRead:
        node = await self._uow.nodes.live(node_id)
        if node.kb_id != self._agent.kb_id or (kind is not None and node.kind != kind):
            raise NotFoundError(f"{kind or 'node'} {node_id} not found", {"id": str(node_id)})
        return node

    async def _propose(self, payload: ProposalPayload) -> ProposalRead:
        proposal = await self._proposals.create(
            ProposalCreate(kb_id=self._agent.kb_id, agent_id=self._agent.id, payload=payload)
        )
        await enqueue_refresh(self._jobs, proposal)
        return proposal

    async def _file(self, text: str, uploads: list[Upload]) -> Filed:
        """Posted to the agent's latest conversation, or a new one; its job runs as a chat message's does."""
        kb_id, agent_id = self._agent.kb_id, self._agent.id
        conversations = await self._conversations.list(kb_id, agent_id)
        conversation = conversations[0] if conversations else None
        if conversation is None:
            conversation = await self._conversations.create(kb_id, ConversationStart(agent_id=agent_id))
        posted = await self._conversations.post(conversation.id, text, uploads, None, route="guardar")
        return await self._filed(await self._wait(posted.reply))

    async def get_reply(self, reply_id: UUID) -> Filed:
        """Where a filing stands now, for an agent whose wait ended while the job was still working."""
        reply = await self._uow.messages.get(reply_id)
        conversation = await self._uow.conversations.get(reply.conversation_id)
        if conversation.agent_id != self._agent.id or reply.role != "acervo":
            raise NotFoundError(f"reply {reply_id} not found", {"id": str(reply_id)})
        return await self._filed(reply)

    async def _filed(self, reply: MessageRead) -> Filed:
        return Filed(
            reply_id=reply.id,
            status=reply.status,
            reply=reply.text,
            error=reply.error,
            run_id=reply.run_id,
            proposals=await self._uow.proposals.of_message(reply.id),
        )

    async def _wait(self, reply: MessageRead) -> MessageRead:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._wait_seconds
        while True:
            # Ends the transaction, so each look sees what the worker committed and no connection is held between.
            await self._uow.rollback()
            reply = await self._uow.messages.get(reply.id)
            if reply.status != "working" or loop.time() >= deadline:
                return reply
            await asyncio.sleep(POLL_SECONDS)


def _section(markdown: str, wanted: str) -> tuple[Section, int, int]:
    """The section whose anchor or heading is `wanted`, with its heading's line and the line after its last."""
    found = next((section for section in sections(markdown) if wanted in (section.anchor, section.heading)), None)
    if found is None:
        raise NotFoundError(f"section {wanted!r} not in the page", {"section": wanted})
    start, end = span(markdown.splitlines(), found.anchor)
    return Section(anchor=found.anchor, heading=found.heading), start, end
