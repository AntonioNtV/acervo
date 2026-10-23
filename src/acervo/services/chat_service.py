import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.core.errors import AcervoError, NotFoundError, ValidationError
from acervo.core.ids import uuid7
from acervo.core.settings import Thresholds
from acervo.model_clients.chat_agent import ChatAgent, Tool, Turn
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead, AgentUpdate
from acervo.schemas.conversation import Citation, ConversationRead, MessageRead, MessageUpdate
from acervo.schemas.events import (
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    ProposalEvent,
    StepEvent,
    StepName,
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
from acervo.services.agent_tools import AgentTools, Folder, PageContent
from acervo.services.events import EventBus, JobQueue
from acervo.services.filing_service import Filing, FilingService, Origin
from acervo.services.proposal_service import OPEN, ProposalService, enqueue_refresh
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


class CitedPage(PageContent):
    cite: str = Field(description="The marker to write after each claim taken from this page.")


class CitedPdfPage(BaseModel):
    cite: str = Field(description="The marker to write after each claim taken from this page of the PDF.")
    page: int = Field(description="The page, counted from 1.")
    text: str


class CitedPdf(BaseModel):
    node_id: UUID
    path: str
    page_count: int = Field(description="How many pages the PDF has.")
    pages: list[CitedPdfPage]


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

    @property
    def origin(self) -> Origin:
        return Origin(self.agent, self.run_id, self.conversation.id, self.reply.id)

    def cite(
        self, node_id: UUID, kind: Literal["page", "file"], path: str, anchor: str | None, page: int | None
    ) -> str:
        """The marker of a source, the same one each time it is read again."""
        same = next(
            (s for s in self.sources if (s.node_id, s.anchor, s.page) == (node_id, anchor, page)),
            None,
        )
        if same is None:
            same = Citation(
                marker=len(self.sources) + 1, node_id=node_id, kind=kind, path=path, anchor=anchor, page=page
            )
            self.sources.append(same)
        return f"[{same.marker}]"


def _join(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name


def _where(payload: ProposalPayload) -> str:
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


def _undone_path(payload: ProposalPayload) -> str:
    """Where what an applied proposal changed is now."""
    match payload:
        case MovePayload():
            return _join(payload.to_path, payload.from_path.rsplit("/", 1)[-1])
        case RenamePayload():
            return _join(payload.path.rpartition("/")[0], payload.title)
        case PatchPayload() | ConflictPayload() | ReplacePdfPayload() | UndoPayload():
            return payload.path
        case CreatePagePayload() | SavePdfPayload():
            return _where(payload)


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
            done = await self._run(run)
        except asyncio.CancelledError as exc:
            # A job past its timeout is cancelled: its reply must not stay working.
            logger.warning("message %s cancelled", message_id)
            await self._fail(run, exc)
            raise
        except Exception as exc:
            logger.exception("message %s failed", message_id)
            return await self._fail(run, exc)
        await self._events.publish(conversation.id, MessageEvent(message=done))
        await self._events.publish(conversation.id, DoneEvent(message_id=done.id))
        return done

    async def _run(self, run: _Run) -> MessageRead:
        if run.reply.replaces_id is not None:
            await self._drop(run, run.reply.replaces_id)
        reply = await (self._converse(run) if run.agent.built_in else self._file(run))
        done = await self._uow.messages.update(run.reply.id, reply)
        await self._uow.commit()
        return done

    async def _converse(self, run: _Run) -> MessageUpdate:
        async def on_text(text: str) -> None:
            await self._events.publish(run.conversation.id, DeltaEvent(message_id=run.reply.id, text=text))

        text = await self._chat.reply(await self._prompt(run), await self._turns(run), self._tools(run), on_text)
        # Applied only now: a run that fails on the way leaves each of its proposals unapplied, and drops them.
        for proposal, placed in run.proposed:
            settled, failed = await self._settle(run, proposal, placed)
            if failed is not None:
                text += f"\n\n{KIND[settled.kind]}: {_where(settled.payload)} · não foi aplicada ({failed})."
        cited = [source for source in run.sources if f"[{source.marker}]" in text]
        return MessageUpdate(text=text, citations=cited, grounded=bool(cited) or run.filed, status="done")

    async def _file(self, run: _Run) -> MessageUpdate:
        """The message's files, or else its text as a fact, each filed before any is applied."""
        message = run.message
        if message.attachments:
            filings = [await self._filing.attachment(attachment, run.origin) for attachment in message.attachments]
        else:
            filings = [await self._filing.fact(message.text, run.origin)]
        lines = []
        for filing in filings:
            if filing.proposal is None:
                lines.append(f"Já está escrito em {_written(filing)}.")
                continue
            proposal, failed = await self._settle(run, filing.proposal, filing.placed)
            what = f"{KIND[proposal.kind]}: {_where(proposal.edited_payload or proposal.payload)}"
            if proposal.status == "applied":
                lines.append(f"{what} · aplicada.")
            elif failed is not None:
                lines.append(f"{what} · não foi aplicada ({failed}); esperando aprovação.")
            elif not filing.placed:
                lines.append("Não sei onde guardar; escolha um dos lugares sugeridos.")
            else:
                lines.append(f"{what} · esperando aprovação.")
        return MessageUpdate(text="\n".join(lines), grounded=True, status="done")

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

    def _tools(self, run: _Run) -> list[Tool]:
        """The base's tools, bound to the run: the reads MCP agents use, and writes that make proposals."""
        base = AgentTools(self._uow, self._storage, self._jobs, self._events, run.agent)

        async def list_folder(node_id: UUID | None = None) -> Folder:
            """What is right under a folder or page: each child's id, kind, title and description.

            Args:
                node_id: A folder or page; omitted for the base's root.
            """
            folder = await base.list_folder(node_id)
            await self._step(run, "list_folder", folder.path or None)
            return folder

        async def read_page(node_id: UUID, section: str | None = None) -> CitedPage:
            """A page's Markdown as the person last typed it, whole or one `##` section.

            Args:
                node_id: The page.
                section: A section's anchor or heading; omitted for the whole page.
            """
            page = await base.read_page(node_id, section)
            await self._step(run, "read_page", page.path)
            cite = run.cite(page.node_id, "page", page.path, page.section, None)
            return CitedPage(**page.model_dump(), cite=cite)

        async def read_pdf_pages(node_id: UUID, first: int, last: int) -> CitedPdf:
            """The text of a few pages of a PDF of the base, never all of it.

            Args:
                node_id: The PDF.
                first: The first page, counted from 1.
                last: The last page; a few pages after `first` at most.
            """
            read = await base.read_pdf_pages(node_id, first, last)
            await self._step(run, "read_pdf_pages", f"{read.path} · {read.first}–{read.last}")
            pages = [
                CitedPdfPage(cite=run.cite(read.node_id, "file", read.path, None, number), page=number, text=text)
                for number, text in enumerate(read.pages, read.first)
            ]
            return CitedPdf(node_id=read.node_id, path=read.path, page_count=read.page_count, pages=pages)

        async def file_fact(text: str) -> Proposed:
            """Files a fact the person brought: where it goes, whether it is already written or contradicts a page
            is decided here, and the result is a proposal the person approves.

            Args:
                text: The fact, in plain words, standing on its own.
            """
            await self._step(run, "file_fact", text)
            return await self._proposed(run, await self._filing.fact(text, run.origin))

        async def file_attachment(name: str) -> Proposed:
            """Files a PDF attached to the message: saved in the right folder or as a new version of one there,
            as a proposal the person approves.

            Args:
                name: The attached file's name.
            """
            attachment = next((attachment for attachment in run.message.attachments if attachment.name == name), None)
            if attachment is None:
                raise ValidationError(f"nenhum anexo se chama {name}", {"name": name})
            await self._step(run, "file_attachment", name)
            return await self._proposed(run, await self._filing.attachment(attachment, run.origin))

        async def move(node_id: UUID, parent_id: UUID | None) -> Proposed:
            """Proposes moving a folder, page or file under another folder or page.

            Args:
                node_id: What to move.
                parent_id: The folder or page it goes under; null for the base's root.
            """
            payload = await base.move_payload(node_id, parent_id)
            await self._step(run, "move", payload.from_path)
            return await self._propose(run, payload)

        async def rename(node_id: UUID, title: str) -> Proposed:
            """Proposes a new title for a folder, page or file.

            Args:
                node_id: What to rename.
                title: The new title.
            """
            payload = await base.rename_payload(node_id, title)
            await self._step(run, "rename", payload.path)
            return await self._propose(run, payload)

        async def undo_last() -> Proposed:
            """Proposes undoing the change applied last in the base."""
            await self._step(run, "undo_last")
            last = await self._uow.proposals.last_applied(run.conversation.kb_id)
            if last is None:
                return Proposed(outcome="nothing_to_undo")
            payload = UndoPayload(proposal_id=last.id, path=_undone_path(last.edited_payload or last.payload))
            return await self._propose(run, payload)

        return [list_folder, read_page, read_pdf_pages, file_fact, file_attachment, move, rename, undo_last]

    async def _propose(self, run: _Run, payload: ProposalPayload) -> Proposed:
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

    async def _proposed(self, run: _Run, filing: Filing) -> Proposed:
        run.filed = True
        if filing.proposal is None:
            return Proposed(outcome="already_written", where=_written(filing))
        proposal = filing.proposal
        run.proposed.append((proposal, filing.placed))
        await self._events.publish(run.conversation.id, ProposalEvent(proposal=proposal))
        return Proposed(
            outcome="proposed" if filing.placed else "not_sure",
            kind=proposal.kind,
            where=_where(proposal.payload),
            options=[] if filing.placed else [option.path or "raiz" for option in proposal.alternatives or []],
        )

    async def _settle(self, run: _Run, proposal: ProposalRead, placed: bool) -> tuple[ProposalRead, str | None]:
        """Applied at once for an agent in auto mode, or left pending, also when that apply fails (with why)."""
        failed = None
        try:
            proposal = await self._proposals.auto_accept(proposal, placed)
        except Exception as exc:
            logger.exception("proposal %s was not applied", proposal.id)
            await self._uow.rollback()
            proposal, failed = await self._uow.proposals.get(proposal.id), str(exc)
        await self._events.publish(run.conversation.id, ProposalEvent(proposal=proposal))
        await enqueue_refresh(self._jobs, proposal)
        return proposal, failed

    async def _drop(self, run: _Run, reply_id: UUID) -> None:
        """What a reply's pending or stale proposals proposed is no longer asked: the system's rejection, not the
        person's, so no reason labels it. Applied ones stay."""
        for proposal in await self._uow.proposals.of_message(reply_id):
            if proposal.status in OPEN:
                dropped = await self._uow.proposals.update(proposal.id, ProposalUpdate(status="rejected"))
                await self._events.publish(run.conversation.id, ProposalEvent(proposal=dropped))
        await self._uow.commit()

    async def _fail(self, run: _Run, exc: BaseException) -> MessageRead:
        """Nothing of the run is left waiting or applied; the decisions it asked stay logged, once (the filing logs
        them)."""
        await self._uow.rollback()
        await self._drop(run, run.reply.id)
        code = exc.code if isinstance(exc, AcervoError) else "internal"
        error = INTERRUPTED if isinstance(exc, asyncio.CancelledError) else str(exc)
        failed = await self._uow.messages.update(run.reply.id, MessageUpdate(status="failed", error=error))
        await self._uow.commit()
        await self._events.publish(run.conversation.id, MessageEvent(message=failed))
        await self._events.publish(run.conversation.id, ErrorEvent(message_id=failed.id, error=code, message=error))
        return failed

    async def _step(self, run: _Run, step: StepName, detail: str | None = None) -> None:
        await self._events.publish(run.conversation.id, StepEvent(message_id=run.reply.id, step=step, detail=detail))
