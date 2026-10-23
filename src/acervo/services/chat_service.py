import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import BinaryContent, ModelRetry, ToolReturn

from acervo.core.errors import AcervoError, NotFoundError, ValidationError
from acervo.core.ids import uuid7
from acervo.core.settings import Thresholds
from acervo.domain.index import Block, SearchStep
from acervo.model_clients.chat_agent import (
    ChatAgent,
    Chunk,
    Tool,
    Turn,
    end_chunks,
    metadata_chunk,
    start_chunk,
    text_chunks,
    with_data,
)
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead, AgentUpdate
from acervo.schemas.conversation import (
    Citation,
    ConversationRead,
    MessageRead,
    MessageUpdate,
    UiActivity,
    UiActivityPart,
    UiMetadata,
    UiProposalPart,
    UiSourcePart,
)
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    MovePayload,
    PatchPayload,
    ProposalCreate,
    ProposalPayload,
    ProposalRead,
    ProposalUpdate,
    RenamePayload,
    ReplacePdfPayload,
    SavePdfPayload,
    UndoPayload,
)
from acervo.services.agent_tools import AgentTools, Fetched, Folder
from acervo.services.events import EventBus, JobQueue
from acervo.services.filing_service import Filing, FilingService, Origin
from acervo.services.proposal_service import OPEN, ProposalService
from acervo.services.search_service import Cited
from acervo.services.storage import Storage

# The earlier messages the chat reads, when the caller does not say (the worker passes `Settings.chat_history`).
HISTORY = 20
INTERRUPTED = "a mensagem foi interrompida antes de terminar"
KIND: dict[str, str] = {
    "append": "Acréscimo",
    "edit": "Edição",
    "create_page": "Página nova",
    "conflict": "Conflito",
    "save_pdf": "Salvar PDF",
    "replace_pdf": "Nova versão",
    "move": "Mover",
    "rename": "Renomear",
    "undo": "Desfazer",
}

logger = logging.getLogger(__name__)


class Excerpt(BaseModel):
    """The part of a passage on one page of a PDF, or the whole passage of a page."""

    cite: str = Field(description="The marker to write after each claim taken from this excerpt.")
    page: int | None = Field(description="The PDF's page; null for a page.")
    text: str


class Found(BaseModel):
    """A passage the search kept, best first."""

    ref: str = Field(description="Opens the passage's section with `abrir`.")
    node_id: UUID = Field(description="The page or the PDF.")
    path: str = Field(description="Its path, joined by /.")
    section: str = Field(description="The section's title.")
    excerpts: list[Excerpt] = Field(description="The passage, a page of the PDF at a time.")


class Results(BaseModel):
    evidence: list[Found] = Field(description="Empty when nothing in the base answers the question.")
    looked_in: list[str] = Field(description="The folders and documents the search reached, to say where it looked.")


class Opened(Fetched):
    cite: str | None = Field(
        default=None, description="The marker for claims taken from a section's `text`; null for the outline."
    )
    page_cites: dict[int, str] = Field(
        default={}, description="For pages of a PDF: each page's marker, for claims taken from that page."
    )


class CitedImage(BaseModel):
    cite: str = Field(description="The marker to write after each claim taken from this page's image.")
    page: int = Field(description="The page, counted from 1; its image follows the result.")


class CitedImages(BaseModel):
    node_id: UUID
    path: str
    page_count: int = Field(description="How many pages the PDF has.")
    pages: list[CitedImage]


class Proposed(BaseModel):
    """What a write tool did: a proposal the person sees in the thread, or why there is none."""

    outcome: Literal["proposed", "not_sure", "already_written", "nothing_to_undo"] = Field(
        description="proposed: waiting for the person; not_sure: no clear place, the person picks one of `options`; "
        "already_written: nothing to add, it is at `where`."
    )
    kind: str | None = Field(default=None, description="The proposal's kind.")
    where: str | None = Field(default=None, description="Where it goes or what it changes.")
    options: list[str] = Field(default_factory=list, description="The places the person picks from.")


@dataclass
class _Run:
    message: MessageRead
    reply: MessageRead
    conversation: ConversationRead
    agent: AgentRead
    run_id: UUID = field(default_factory=uuid7)
    # Each proposal made, pending until the run ends, and whether it has a clear place.
    proposed: list[tuple[ProposalRead, bool]] = field(default_factory=list)
    sources: list[Citation] = field(default_factory=list)
    # A write tool ran: the reply is about the base even when nothing was proposed ("já está escrito").
    filed: bool = False
    # The reply's stream started: its `start` went out.
    streamed: bool = False

    @property
    def origin(self) -> Origin:
        return Origin(self.agent, self.run_id, self.conversation.id, self.reply.id)

    def cite(
        self,
        node_id: UUID,
        kind: Literal["page", "file"],
        path: str,
        anchor: str | None,
        page: int | None,
        block_id: str | None = None,
        highlight: tuple[float, float, float, float] | None = None,
    ) -> str:
        """The marker of a source, the same one each time it is read or found again."""
        key = (node_id, anchor, page, block_id)
        same = next((s for s in self.sources if (s.node_id, s.anchor, s.page, s.block_id) == key), None)
        if same is None:
            same = Citation(
                marker=len(self.sources) + 1,
                node_id=node_id,
                kind=kind,
                path=path,
                anchor=anchor,
                page=page,
                block_id=block_id,
                highlight=list(highlight) if highlight else None,
            )
            self.sources.append(same)
        return f"[{same.marker}]"


async def fail_interrupted(uow: UnitOfWork, timeout_seconds: int) -> None:
    """A reply still working past the job timeout lost its job with the worker that ran it, and arq does not run a
    job again (`max_tries` 1): it is failed, so it never stays working."""
    await uow.messages.fail_working(datetime.now(UTC) - timedelta(seconds=timeout_seconds), INTERRUPTED)
    await uow.commit()


@contextmanager
def _retried() -> Iterator[None]:
    """A read that fails on what the model asked (a page out of range, a node gone) is told to the model to try
    again, instead of failing the run."""
    try:
        yield
    except AcervoError as exc:
        raise ModelRetry(exc.message) from exc


def _activity(step: SearchStep) -> Chunk:
    """The reply's activity line while the search is at `step`."""
    if step.stage == "folder":
        label = f"Procurando em {step.label}"
    else:
        label = f"Lendo {step.label}" + (f", p. {step.page}" if step.page else "")
    return UiActivityPart(data=UiActivity(label=label, stage=step.stage)).model_dump_json()


def _join(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name


def where(payload: ProposalPayload) -> str:
    match payload:
        case PatchPayload() | ConflictPayload():
            return f"{payload.path} › {payload.heading}" if payload.heading else payload.path
        case CreatePagePayload():
            return _join(payload.parent_path, payload.title)
        case SavePdfPayload():
            return _join(payload.parent_path, payload.name)
        case MovePayload():
            return f"{payload.from_path} → {payload.to_path or 'raiz'}"
        case RenamePayload():
            return f"{payload.path} → {payload.title}"
        case ReplacePdfPayload() | UndoPayload():
            return payload.path


def _proposal_chunk(proposal: ProposalRead) -> Chunk:
    return UiProposalPart(id=proposal.id, data=proposal).model_dump_json()


def _written(filing: Filing) -> str:
    assert filing.written is not None
    written = filing.written
    return f"{written.path} › {written.heading}" if written.heading else written.path


class ChatService:
    """Runs one message: the built-in chat answers it as an agent with the base's tools; a message of an external
    agent is filed straight through the Curator. Every change is a proposal, stored pending and applied, for an agent
    in auto mode, only once the run ended well; the reply and its steps stream to the chat."""

    def __init__(
        self,
        uow: UnitOfWork,
        storage: Storage,
        decider: Decider,
        writer: Writer,
        thresholds: Thresholds,
        events: EventBus,
        jobs: JobQueue,
        chat: ChatAgent,
        history: int = HISTORY,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._events = events
        self._jobs = jobs
        self._chat = chat
        self._history = history
        self._decider = decider
        self._proposals = ProposalService(uow, storage)
        self._filing = FilingService(uow, storage, decider, writer, thresholds)

    async def handle(self, message_id: UUID, reply_id: UUID) -> MessageRead:
        message = await self._uow.messages.get(message_id)
        reply = await self._uow.messages.get(reply_id)
        conversation = await self._uow.conversations.get(reply.conversation_id)
        run = _Run(message, reply, conversation, await self._uow.agents.get(conversation.agent_id))
        run.reply = await self._uow.messages.update(reply.id, MessageUpdate(run_id=run.run_id))
        if run.agent.built_in:
            # An external agent is used when its token is accepted; the chat, when it handles a message.
            await self._uow.agents.update(run.agent.id, AgentUpdate(last_used_at=datetime.now(UTC)))
        await self._uow.commit()
        try:
            return await self._run(run)
        except asyncio.CancelledError as exc:
            # A job past its timeout is cancelled: its reply must not stay working.
            logger.warning("message %s cancelled", message_id)
            await self._fail(run, exc)
            raise
        except Exception as exc:
            logger.exception("message %s failed", message_id)
            return await self._fail(run, exc)

    async def _run(self, run: _Run) -> MessageRead:
        if run.reply.replaces_id is not None:
            await self._drop(run.reply.replaces_id)
        reply = await (self._converse(run) if run.agent.built_in else self._file(run))
        done = await self._uow.messages.update(run.reply.id, reply)
        # Committed after its stream ended: a reader that finds the reply finished finds its whole stream kept.
        await self._uow.commit()
        return done

    async def _converse(self, run: _Run) -> MessageUpdate:
        update = MessageUpdate()

        async def finish(text: str) -> list[Chunk]:
            # Applied only now: a run that fails on the way leaves each of its proposals unapplied, and drops them.
            chunks, notes = [], []
            for proposal, placed in run.proposed:
                settled, failed = await self._settle(proposal, placed)
                chunks.append(_proposal_chunk(settled))
                if failed is not None:
                    notes.append(f"{KIND[settled.kind]}: {where(settled.payload)} · não foi aplicada ({failed}).")
            for note in notes:
                chunks += text_chunks(note)
            text = "\n\n".join([text, *notes])
            cited = [source for source in run.sources if f"[{source.marker}]" in text]
            chunks += [UiSourcePart.of(source).model_dump_json() for source in cited]
            update.text, update.citations, update.grounded = text, cited, bool(cited) or run.filed
            update.status = "done"
            chunks.append(metadata_chunk(UiMetadata(status="done", grounded=update.grounded).model_dump(mode="json")))
            return chunks

        prompt, turns = await self._prompt(run), await self._turns(run)
        reads, writes = self._tools(run)
        limits = self._storage.settings.retrieval_limits
        stream = self._chat.stream(
            prompt, turns, reads, writes, limits=limits, message_id=str(run.reply.id), finish=finish
        )
        run.streamed = True  # its first chunk is `start`
        async for chunk in stream:
            await self._publish(run, chunk)
        return update

    async def _file(self, run: _Run) -> MessageUpdate:
        """The message's files, or else its text as a fact, each filed before any is applied."""
        message = run.message
        if message.attachments:
            filings = [await self._filing.attachment(attachment, run.origin) for attachment in message.attachments]
        else:
            filings = [await self._filing.fact(message.text, run.origin)]
        lines, chunks = [], []
        for filing in filings:
            if filing.proposal is None:
                lines.append(f"Já está escrito em {_written(filing)}.")
                continue
            proposal, failed = await self._settle(filing.proposal, filing.placed)
            chunks.append(_proposal_chunk(proposal))
            what = f"{KIND[proposal.kind]}: {where(proposal.edited_payload or proposal.payload)}"
            if proposal.status == "applied":
                lines.append(f"{what} · aplicada.")
            elif failed is not None:
                lines.append(f"{what} · não foi aplicada ({failed}); esperando aprovação.")
            elif not filing.placed:
                lines.append("Não sei onde guardar; escolha um dos lugares sugeridos.")
            else:
                lines.append(f"{what} · esperando aprovação.")
        text = "\n".join(lines)
        metadata = metadata_chunk(UiMetadata(status="done", grounded=True).model_dump(mode="json"))
        run.streamed = True
        await self._publish(run, start_chunk(str(run.reply.id)), *text_chunks(text), *chunks, metadata, *end_chunks())
        return MessageUpdate(text=text, grounded=True, status="done")

    async def _prompt(self, run: _Run) -> str:
        message = run.message
        context = []
        if message.context is not None and message.context.page_id is not None:
            try:
                path = await self._uow.nodes.path(message.context.page_id)
                context.append(f"Página aberta: {path} (node_id {message.context.page_id})")
            except (NotFoundError, ValidationError):
                pass
        if message.context is not None and message.context.selection:
            context.append(f"Trecho selecionado na página: {message.context.selection}")
        if message.attachments:
            context.append(f"Arquivos anexados: {', '.join(attachment.name for attachment in message.attachments)}")
        if not context:
            return message.text
        return "\n".join([message.text, "", "Contexto:", *(f"- {line}" for line in context)])

    async def _turns(self, run: _Run) -> list[Turn]:
        """The conversation before the message, without failed or unfinished replies."""
        thread = await self._uow.messages.of_conversation(run.conversation.id)
        before = thread[: next(i for i, sent in enumerate(thread) if sent.id == run.message.id)]
        return [(sent.role, sent.text) for sent in before if sent.status == "done" and sent.text][-self._history :]

    def _tools(self, run: _Run) -> tuple[list[Tool], list[Tool]]:
        """The base's tools, bound to the run: reads, each on a unit of work of its own so they run in parallel, and
        writes that make proposals, one at a time on the run's."""
        base = AgentTools(self._uow, self._storage, self._jobs, self._events, run.agent)

        def reader(uow: UnitOfWork) -> AgentTools:
            return AgentTools(uow, self._storage, self._jobs, self._events, run.agent)

        async def buscar(pergunta: str) -> Results:
            """Searches the base for the passages that answer a question, each with its marker.

            Args:
                pergunta: The question, standing on its own: with the subject the conversation gives it.
            """

            async def step(at: SearchStep) -> None:
                await self._publish(run, _activity(at))

            # Not retried: a decider that fails fails the reply visibly; there is no other way of searching.
            async with self._uow.another() as uow:
                searched = await reader(uow).search(
                    pergunta, self._decider, run_id=run.run_id, message_id=run.reply.id, on_step=step
                )
                blocks: dict[str, Block] = {}
                for node_id in {c.node_id for c in searched.evidence if c.kind == "file"}:
                    found = await uow.indexes.get(node_id)
                    blocks |= {f"{node_id}:{b.id}": b for b in found.parsed.blocks} if found and found.parsed else {}

            def excerpts(c: Cited) -> list[Excerpt]:
                """A passage across PDF pages is cited by the page a claim is on, at that page's first block."""
                on = [b for b in (blocks.get(f"{c.node_id}:{id}") for id in c.block_ids) if b is not None]
                pages = list(dict.fromkeys(b.page for b in on))
                path = "/".join(c.path)
                if len(pages) < 2:
                    cite = run.cite(c.node_id, c.kind, path, c.anchor, c.page, c.block_id, c.highlight)
                    return [Excerpt(cite=cite, page=c.page, text=c.text)]
                split = []
                for page in pages:
                    here = [b for b in on if b.page == page]
                    cite = run.cite(c.node_id, c.kind, path, None, page, here[0].id, here[0].bbox)
                    split.append(Excerpt(cite=cite, page=page, text="\n".join(b.text for b in here)))
                return split

            evidence = [
                Found(
                    ref=c.ref, node_id=c.node_id, path="/".join(c.path), section=c.section_title, excerpts=excerpts(c)
                )
                for c in searched.evidence
            ]
            return Results(evidence=evidence, looked_in=searched.looked_in)

        async def abrir(
            ref: str, section: str | None = None, first: int | None = None, last: int | None = None, offset: int = 0
        ) -> Opened:
            """Opens a page or a PDF where the search pointed: its outline, one section's text, or up to 5 pages of
            a PDF's text.

            Args:
                ref: A page's or a PDF's node_id, or an evidence's ref, which opens its section.
                section: A section's id from the outline; omitted for the outline.
                first: The first page of a PDF to read, counted from 1.
                last: The last page to read; at most 4 after `first`.
                offset: Where the outline goes on from, when it said `remaining`.
            """
            async with self._uow.another() as uow:
                with _retried():
                    fetched = await reader(uow).fetch(ref, section, first, last, offset)
            opened = Opened(**fetched.model_dump())
            if fetched.kind == "page" and fetched.text:
                opened.cite = run.cite(fetched.node_id, "page", fetched.path, fetched.section, None)
            elif fetched.section is not None:
                opened.cite = run.cite(fetched.node_id, "file", fetched.path, None, fetched.first)
            elif fetched.first is not None and fetched.last is not None:
                opened.page_cites = {
                    page: run.cite(fetched.node_id, "file", fetched.path, None, page)
                    for page in range(fetched.first, fetched.last + 1)
                }
            return opened

        async def ver_paginas(node_id: UUID, first: int, last: int | None = None) -> ToolReturn:
            """Up to 2 pages of a PDF as images, for what their text does not show: charts, tables, scans.

            Args:
                node_id: The PDF.
                first: The first page, counted from 1.
                last: The last page; at most 1 after `first`.
            """
            async with self._uow.another() as uow:
                with _retried():
                    viewed = await reader(uow).view_pages(node_id, first, last)
            pages = [
                CitedImage(cite=run.cite(viewed.node_id, "file", viewed.path, None, number), page=number)
                for number in range(viewed.first, viewed.last + 1)
            ]
            return ToolReturn(
                return_value=CitedImages(
                    node_id=viewed.node_id, path=viewed.path, page_count=viewed.page_count, pages=pages
                ),
                content=[BinaryContent(data=image, media_type="image/png") for image in viewed.images],
            )

        async def list_folder(node_id: UUID | None = None) -> Folder:
            """What is right under a folder or page, to find what to move or rename; never to answer a question.

            Args:
                node_id: A folder or page; omitted for the base's root.
            """
            async with self._uow.another() as uow:
                with _retried():
                    return await reader(uow).list_folder(node_id)

        async def file_fact(text: str) -> ToolReturn:
            """Files a fact the person brought: where it goes, whether it is already written or contradicts a page
            is decided here, and the result is a proposal the person approves.

            Args:
                text: The fact, in plain words, standing on its own.
            """
            return await self._proposed(run, await self._filing.fact(text, run.origin))

        async def file_attachment(name: str) -> ToolReturn:
            """Files a PDF attached to the message: saved in the right folder or as a new version of one there,
            as a proposal the person approves.

            Args:
                name: The attached file's name.
            """
            attachment = next((attachment for attachment in run.message.attachments if attachment.name == name), None)
            if attachment is None:
                raise ValidationError(f"nenhum anexo se chama {name}", {"name": name})
            return await self._proposed(run, await self._filing.attachment(attachment, run.origin))

        async def move(node_id: UUID, parent_id: UUID | None) -> ToolReturn:
            """Proposes moving a folder, page or file under another folder or page.

            Args:
                node_id: What to move.
                parent_id: The folder or page it goes under; null for the base's root.
            """
            payload = await base.move_payload(node_id, parent_id)
            return await self._propose(run, payload)

        async def rename(node_id: UUID, title: str) -> ToolReturn:
            """Proposes a new title for a folder, page or file.

            Args:
                node_id: What to rename.
                title: The new title.
            """
            payload = await base.rename_payload(node_id, title)
            return await self._propose(run, payload)

        async def undo_last() -> ToolReturn:
            """Proposes undoing the change applied last in the base."""
            last = await self._uow.proposals.last_applied(run.conversation.kb_id)
            if last is None:
                return with_data(Proposed(outcome="nothing_to_undo"))
            return await self._propose(run, await self._proposals.undo_payload(last))

        return [buscar, abrir, ver_paginas, list_folder], [file_fact, file_attachment, move, rename, undo_last]

    async def _propose(self, run: _Run, payload: ProposalPayload) -> ToolReturn:
        proposal = await self._proposals.add(
            ProposalCreate(
                kb_id=run.conversation.kb_id,
                agent_id=run.agent.id,
                conversation_id=run.conversation.id,
                message_id=run.reply.id,
                run_id=run.run_id,
                payload=payload,
                undo_of=payload.proposal_id if isinstance(payload, UndoPayload) else None,
            )
        )
        await self._uow.commit()
        return await self._proposed(run, Filing(proposal=proposal))

    async def _proposed(self, run: _Run, filing: Filing) -> ToolReturn:
        run.filed = True
        if filing.proposal is None:
            return with_data(Proposed(outcome="already_written", where=_written(filing)))
        proposal = filing.proposal
        run.proposed.append((proposal, filing.placed))
        proposed = Proposed(
            outcome="proposed" if filing.placed else "not_sure",
            kind=proposal.kind,
            where=where(proposal.payload),
            options=[] if filing.placed else [option.path or "raiz" for option in proposal.alternatives or []],
        )
        return with_data(proposed, _proposal_chunk(proposal))

    async def _settle(self, proposal: ProposalRead, placed: bool) -> tuple[ProposalRead, str | None]:
        """Applied at once for an agent in auto mode, or left pending, also when that apply fails (with why); either
        way as it stands now, after whatever the person did to it while the run went on."""
        # Ends the transaction, so the read sees what the person committed meanwhile, not what this session kept.
        await self._uow.rollback()
        failed = None
        try:
            proposal = await self._proposals.auto_accept(proposal, placed)
        except Exception as exc:
            logger.exception("proposal %s was not applied", proposal.id)
            await self._uow.rollback()
            proposal, failed = await self._uow.proposals.get(proposal.id), str(exc)
        return proposal, failed

    async def _drop(self, reply_id: UUID) -> list[ProposalRead]:
        """What a reply's pending or stale proposals proposed is no longer asked: the system's rejection, not the
        person's, so no reason labels it. Applied ones stay."""
        dropped = [
            await self._uow.proposals.update(proposal.id, ProposalUpdate(status="rejected"))
            for proposal in await self._uow.proposals.of_message(reply_id)
            if proposal.status in OPEN
        ]
        await self._uow.commit()
        return dropped

    async def _fail(self, run: _Run, exc: BaseException) -> MessageRead:
        """Nothing of the run is left waiting or applied; the decisions it asked stay logged, once (the filing logs
        them). The stream ends with the error, before the failure is committed."""
        await self._uow.rollback()
        dropped = await self._drop(run.reply.id)
        error = INTERRUPTED if isinstance(exc, asyncio.CancelledError) else str(exc)
        failed = await self._uow.messages.update(run.reply.id, MessageUpdate(status="failed", error=error))
        metadata = UiMetadata(status="failed", grounded=failed.grounded, error=error).model_dump(mode="json")
        # A run that failed before its stream started still streams a whole reply.
        chunks = [] if run.streamed else [start_chunk(str(run.reply.id))]
        chunks += [_proposal_chunk(proposal) for proposal in dropped]
        await self._publish(run, *chunks, metadata_chunk(metadata), *end_chunks(error))
        await self._uow.commit()
        return failed

    async def _publish(self, run: _Run, *chunks: Chunk) -> None:
        for chunk in chunks:
            await self._events.publish(run.reply.id, chunk)
