import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from acervo.core.errors import AcervoError, NotFoundError, ValidationError
from acervo.core.ids import uuid7
from acervo.core.settings import Thresholds
from acervo.domain.cards import (
    ORGANIZE_KINDS,
    ROUTES,
    CardInput,
    ChildDescription,
    OrganizeKind,
    Placement,
    Reading,
    Route,
)
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.pipeline import router
from acervo.pipeline.curator import organize, policy
from acervo.pipeline.curator.tree import PageText, SnapshotNode, TreeSnapshot
from acervo.pipeline.pdf import reader
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead, AgentUpdate
from acervo.schemas.conversation import Attachment, ConversationRead, MessageRead, MessageUpdate
from acervo.schemas.events import DoneEvent, ErrorEvent, MessageEvent, ProposalEvent, StepEvent, StepName
from acervo.schemas.node import NodeUpdate
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    Decision,
    DecisionLogCreate,
    MovePayload,
    PatchPayload,
    ProposalCreate,
    ProposalPayload,
    ProposalRead,
    ProposalUpdate,
    RenamePayload,
    ReplacePdfPayload,
    SavePdfPayload,
    StagedFile,
    UndoPayload,
)
from acervo.services.events import EventBus, JobQueue
from acervo.services.page_service import PageService
from acervo.services.proposal_service import OPEN, ProposalService, enqueue_refresh
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

# The messages before the one handled that the understanding reads.
HISTORY = 6
# How many descriptions are written at once when a tree is described before filing.
DESCRIBING = 4
PDF = "application/pdf"

ASK_FIRST: dict[Route, str] = {
    "perguntar": "procurar a resposta",
    "guardar": "guardar isso na base",
    "organizar": "organizar a base",
    "conversar": "só conversar",
}
ASK_KIND: dict[OrganizeKind, str] = {
    "move": "mover um item",
    "rename": "renomear um item",
    "undo": "desfazer a última mudança",
}
INTERRUPTED = "a mensagem foi interrompida antes de terminar"
NOT_YET = "Responder perguntas chega na próxima fase do Acervo. Se era para guardar, é só mudar abaixo."
CHAT = "Mande um fato, um PDF ou um pedido para mover, renomear ou desfazer, e eu proponho a mudança."
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


@dataclass
class _Outcome:
    """What one part of a message produced: a line of the reply, or a proposal to store once every part ran."""

    line: str = ""
    proposal: ProposalCreate | None = None
    placed: bool = True
    ask: tuple[Reading, ...] | None = None


@dataclass
class _Run:
    reply: MessageRead
    conversation: ConversationRead
    agent: AgentRead
    run_id: UUID = field(default_factory=uuid7)
    log: list[Decision] = field(default_factory=list)
    # Set once the decisions are committed, so a failure after that does not log them again.
    logged: bool = False
    files_filed: bool = False


def _either(options: list[str]) -> str:
    """The options as one question: "Mover um item, renomear um item ou desfazer a última mudança?"."""
    text = f"{', '.join(options[:-1])} ou {options[-1]}?"
    return f"{text[0].upper()}{text[1:]}"


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


def _depth(tree: TreeSnapshot, node: SnapshotNode) -> int:
    depth = 0
    while node.parent_id is not None:
        node, depth = tree.node(node.parent_id), depth + 1
    return depth


class ChatService:
    """Runs one message end to end: understood, filed or organized, every decision logged, proposed through
    `ProposalService` (applied there for an agent in auto mode); the reply and its steps stream to the chat."""

    def __init__(
        self,
        uow: UnitOfWork,
        storage: Storage,
        decider: Decider,
        writer: Writer,
        thresholds: Thresholds,
        events: EventBus,
        jobs: JobQueue,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._decider = decider
        self._writer = writer
        self._thresholds = thresholds
        self._events = events
        self._jobs = jobs
        self._pages = PageService(uow)
        self._tree = TreeService(uow)
        self._proposals = ProposalService(uow, storage)

    async def handle(self, message_id: UUID, reply_id: UUID, route: Reading | None = None) -> MessageRead:
        """`route` redoes the message as the person said it should be read, without asking: a route, or which
        change an organizar is."""
        message = await self._uow.messages.get(message_id)
        reply = await self._uow.messages.get(reply_id)
        conversation = await self._uow.conversations.get(reply.conversation_id)
        run = _Run(reply, conversation, await self._uow.agents.get(conversation.agent_id))
        run.reply = await self._uow.messages.update(reply.id, MessageUpdate(run_id=run.run_id))
        if run.agent.built_in:
            # An external agent is used when its token is accepted; the chat, when it handles a message.
            await self._uow.agents.update(run.agent.id, AgentUpdate(last_used_at=datetime.now(UTC)))
        await self._uow.commit()
        try:
            done = await self._run(run, message, route)
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

    async def refresh_descriptions(self, node_ids: list[UUID]) -> None:
        """Each node and the ones above it describe their children again, unless the person wrote theirs."""
        seen: set[UUID] = set()
        for node_id in node_ids:
            current: UUID | None = node_id
            while current is not None and current not in seen:
                seen.add(current)
                try:
                    node = await self._uow.nodes.live(current)
                except NotFoundError:
                    break
                if node.kind != "file" and not node.description_locked:
                    await self._describe(node.kb_id, node.id, node.title)
                current = node.parent_id
        await self._uow.commit()

    async def _run(self, run: _Run, message: MessageRead, reading: Reading | None) -> MessageRead:
        if run.reply.replaces_id is not None:
            await self._drop(run, run.reply.replaces_id)
        understood, outcomes = await self._work(run, message, reading)
        await self._step(run, "writing")
        stored = await self._store(run, outcomes)
        lines = [await self._settle(run, outcome, proposal) for outcome, proposal in zip(outcomes, stored, strict=True)]
        ask = next((list(outcome.ask) for outcome in outcomes if outcome.ask), None)
        done = await self._uow.messages.update(
            run.reply.id, MessageUpdate(text="\n".join(lines), understood_as=understood, ask=ask, status="done")
        )
        await self._uow.commit()
        return done

    async def _work(
        self, run: _Run, message: MessageRead, reading: Reading | None
    ) -> tuple[Route | None, list[_Outcome]]:
        """Every decision and every text the reply needs, before anything is stored: a failure here leaves the base
        as it was."""
        kind = next((option for option in ORGANIZE_KINDS if option == reading), None)
        route = "organizar" if kind else next((option for option in ROUTES if option == reading), None)
        if route is not None:
            understood: router.Understood = router.Routed(text=message.text, route=route, probability=1.0)
        else:
            await self._step(run, "understanding")
            context = await self._context(run, message)
            understood = await router.route(
                message.text, context, self._decider, self._writer, self._thresholds, run.log
            )
        parts = understood.parts if isinstance(understood, router.Split) else [understood]
        if isinstance(understood, router.Split):
            await self._step(run, "splitting")
        outcomes: list[_Outcome] = []
        tree: TreeSnapshot | None = None
        for part in parts:
            if isinstance(part, router.AskFirst):
                outcomes.append(
                    _Outcome(line=_either([ASK_FIRST[option] for option in part.options]), ask=part.options)
                )
            elif part.route in ("guardar", "organizar"):
                tree = tree or await self._described(run.conversation.kb_id)
                if part.route == "guardar":
                    outcomes += await self._file(run, message, part.text, tree)
                else:
                    outcomes.append(await self._organize(run, part.text, tree, kind))
            else:
                outcomes.append(_Outcome(line=NOT_YET if part.route == "perguntar" else CHAT))
        routed = [part.route for part in parts if isinstance(part, router.Routed)]
        return (routed[0] if routed else None), outcomes

    async def _context(self, run: _Run, message: MessageRead) -> router.RouteContext:
        thread = await self._uow.messages.of_conversation(run.conversation.id)
        index = next(i for i, sent in enumerate(thread) if sent.id == message.id)
        before = [sent.text for sent in thread[:index] if sent.text][-HISTORY:]
        page_path = None
        if message.context is not None and message.context.page_id is not None:
            try:
                # What the person sees is what the pipeline reads.
                await self._pages.cut(message.context.page_id)
                page_path = await self._uow.nodes.path(message.context.page_id)
            except (NotFoundError, ValidationError):
                page_path = None
        return router.RouteContext(
            files=[attachment.name for attachment in message.attachments],
            page_path=page_path,
            selection=message.context.selection if message.context else None,
            history=before,
        )

    async def _file(self, run: _Run, message: MessageRead, text: str, tree: TreeSnapshot) -> list[_Outcome]:
        """The message's files, the first time a part is to be saved; else the part's text as a fact."""
        if message.attachments and not run.files_filed:
            run.files_filed = True
            return [await self._file_pdf(run, attachment, tree) for attachment in message.attachments]
        await self._step(run, "choosing_place")
        source = CardInput(text=text)

        async def read_page(node_id: UUID) -> PageText:
            await self._step(run, "checking_page", tree.path(tree.node(node_id)))
            await self._pages.cut(node_id)
            version = await self._uow.page_versions.current(node_id)
            return PageText(page_id=node_id, version_id=version.id, markdown=version.markdown)

        filed = await policy.file_text(source, tree, read_page, self._decider, self._writer, self._thresholds, run.log)
        if isinstance(filed, policy.AlreadyWritten):
            where = f"{filed.path} › {filed.heading}" if filed.heading else filed.path
            return [_Outcome(line=f"Já está escrito em {where}.")]
        if isinstance(filed, policy.NotSure):
            # A filing's NotSure always carries what waits in "Sem lugar definido".
            assert filed.payload is not None
            return [self._outcome(run, filed.payload, filed.options, placed=False)]
        return [self._outcome(run, filed.payload, filed.alternatives)]

    async def _file_pdf(self, run: _Run, attachment: Attachment, tree: TreeSnapshot) -> _Outcome:
        await self._step(run, "reading_file", attachment.name)
        async with self._storage.download(attachment.storage_key) as path:
            text, outline = await asyncio.to_thread(reader.first_pages, path)
        await self._step(run, "choosing_place", attachment.name)
        source = CardInput(text=text, file_name=attachment.name, outline=outline)
        filed = await policy.file_pdf(source, tree, self._decider, self._writer, self._thresholds, run.log)
        staged = StagedFile(**attachment.model_dump(exclude={"mime"}))
        if isinstance(filed, policy.Propose):
            return self._outcome(run, filed.payload, filed.alternatives, staged=staged)
        assert filed.payload is not None
        return self._outcome(run, filed.payload, filed.options, staged=staged, placed=False)

    async def _organize(self, run: _Run, text: str, tree: TreeSnapshot, kind: OrganizeKind | None) -> _Outcome:
        await self._step(run, "organizing")
        last = await self._uow.proposals.last_applied(run.conversation.kb_id)
        last_applied = None
        if last is not None:
            path = _undone_path(last.edited_payload or last.payload)
            last_applied = organize.LastApplied(proposal_id=last.id, path=path)
        result = await organize.organize(text, tree, last_applied, self._decider, self._thresholds, run.log, kind)
        match result:
            case organize.AskKind():
                return _Outcome(line=_either([ASK_KIND[option] for option in result.options]), ask=result.options)
            case policy.Propose():
                return self._outcome(run, result.payload, result.alternatives)
            case organize.NeedsTitle():
                return _Outcome(line=f"Qual é o novo nome de {result.path}?")
            case organize.NothingToUndo():
                return _Outcome(line="Não há mudança aplicada para desfazer.")
            case policy.NotSure():
                paths = [option.path or "raiz" for option in result.options]
                if not paths:
                    return _Outcome(line="Não encontrei o que mudar; diga o caminho.")
                return _Outcome(line=f"Não tenho certeza: {', '.join(paths)}? Diga qual.")

    def _outcome(
        self,
        run: _Run,
        payload: ProposalPayload,
        alternatives: list[Placement] | None,
        staged: StagedFile | None = None,
        placed: bool = True,
    ) -> _Outcome:
        proposal = ProposalCreate(
            kb_id=run.conversation.kb_id,
            agent_id=run.agent.id,
            conversation_id=run.conversation.id,
            message_id=run.reply.id,
            run_id=run.run_id,
            payload=payload,
            alternatives=alternatives or None,
            staged=staged,
            undo_of=payload.proposal_id if isinstance(payload, UndoPayload) else None,
        )
        return _Outcome(proposal=proposal, placed=placed)

    async def _store(self, run: _Run, outcomes: list[_Outcome]) -> list[ProposalRead | None]:
        """The run's decisions and every part's proposal, pending, in one transaction: a failure before it leaves
        nothing behind; after it, each proposal stands on its own."""
        await self._log(run)
        stored = [await self._proposals.add(outcome.proposal) if outcome.proposal else None for outcome in outcomes]
        await self._uow.commit()
        run.logged = True
        return stored

    async def _settle(self, run: _Run, outcome: _Outcome, proposal: ProposalRead | None) -> str:
        """A part's line of the reply: its proposal applied at once for an agent in auto mode, or left pending,
        also when that apply fails."""
        if proposal is None:
            return outcome.line
        failed = None
        try:
            proposal = await self._proposals.auto_accept(proposal, outcome.placed)
        except Exception as exc:
            logger.exception("proposal %s was not applied", proposal.id)
            await self._uow.rollback()
            proposal, failed = await self._uow.proposals.get(proposal.id), str(exc)
        await self._events.publish(run.conversation.id, ProposalEvent(proposal=proposal))
        await enqueue_refresh(self._jobs, proposal)
        what = f"{KIND[proposal.kind]}: {_where(proposal.edited_payload or proposal.payload)}"
        if proposal.status == "applied":
            return f"{what} · aplicada."
        if failed is not None:
            return f"{what} · não foi aplicada ({failed}); esperando aprovação."
        if not outcome.placed:
            return "Não sei onde guardar; escolha um dos lugares sugeridos."
        return f"{what} · esperando aprovação."

    async def _described(self, kb_id: UUID) -> TreeSnapshot:
        """The base's tree, each folder or page with children described first when it has no description yet."""
        tree = await self._tree.snapshot(kb_id)
        missing = [node for node in tree.nodes if node.kind != "file" and not node.description and tree.children(node)]
        limit = asyncio.Semaphore(DESCRIBING)

        async def describe(node: SnapshotNode) -> str:
            children = [
                ChildDescription(title=child.title, kind=child.kind, description=child.description)
                for child in tree.children(node)
            ]
            async with limit:
                return await self._writer.describe(node.title, children)

        # Deepest first: a node's description is written from its children's, so each depth waits for the one below.
        for depth in sorted({_depth(tree, node) for node in missing}, reverse=True):
            level = [node for node in missing if _depth(tree, node) == depth]
            for node, description in zip(level, await asyncio.gather(*map(describe, level)), strict=True):
                await self._uow.nodes.update(node.id, NodeUpdate(description=description))
                tree.nodes[tree.nodes.index(node)] = node.model_copy(update={"description": description})
        await self._uow.commit()
        return tree

    async def _describe(self, kb_id: UUID, node_id: UUID, title: str) -> str:
        children = [
            ChildDescription(title=child.title, kind=child.kind, description=child.description)
            for child in await self._uow.nodes.children(kb_id, node_id)
        ]
        if not children:
            return ""
        description = await self._writer.describe(title, children)
        await self._uow.nodes.update(node_id, NodeUpdate(description=description))
        return description

    async def _log(self, run: _Run) -> None:
        await self._uow.decisions.create_many(
            [
                DecisionLogCreate(run_id=run.run_id, message_id=run.reply.id, **decision.model_dump())
                for decision in run.log
            ]
        )

    async def _drop(self, run: _Run, reply_id: UUID) -> None:
        """What a reply's pending or stale proposals proposed is no longer asked: the system's rejection, not the
        person's, so no reason labels it. Applied ones stay."""
        for proposal in await self._uow.proposals.of_message(reply_id):
            if proposal.status in OPEN:
                dropped = await self._uow.proposals.update(proposal.id, ProposalUpdate(status="rejected"))
                await self._events.publish(run.conversation.id, ProposalEvent(proposal=dropped))
        await self._uow.commit()

    async def _fail(self, run: _Run, exc: BaseException) -> MessageRead:
        """Nothing of the run is left waiting; the decisions it asked stay logged, once."""
        await self._uow.rollback()
        await self._drop(run, run.reply.id)
        if not run.logged:
            await self._log(run)
        code = exc.code if isinstance(exc, AcervoError) else "internal"
        error = INTERRUPTED if isinstance(exc, asyncio.CancelledError) else str(exc)
        failed = await self._uow.messages.update(run.reply.id, MessageUpdate(status="failed", error=error))
        await self._uow.commit()
        await self._events.publish(run.conversation.id, MessageEvent(message=failed))
        await self._events.publish(run.conversation.id, ErrorEvent(message_id=failed.id, error=code, message=error))
        return failed

    async def _step(self, run: _Run, step: StepName, detail: str | None = None) -> None:
        await self._events.publish(run.conversation.id, StepEvent(message_id=run.reply.id, step=step, detail=detail))
