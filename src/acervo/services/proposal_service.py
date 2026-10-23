import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import BinaryIO, Literal
from uuid import UUID

from acervo.core.errors import AcervoError, ConflictError, NotFoundError, ValidationError
from acervo.domain import patch
from acervo.domain.patch import Patch, Stale
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeAdd, NodeMove
from acervo.schemas.proposal import (
    AcceptedBy,
    ConflictPayload,
    CreatePagePayload,
    MovePayload,
    PatchPayload,
    ProposalCreate,
    ProposalPayload,
    ProposalRead,
    ProposalSummary,
    ProposalUpdate,
    RejectReason,
    RenamePayload,
    ReplacePdfPayload,
    SavePdfPayload,
    StagedFile,
    UndoPayload,
)
from acervo.services.events import JobQueue
from acervo.services.file_service import FileService
from acervo.services.page_service import PageService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

OPEN = ("pending", "stale")
REFRESH_DESCRIPTIONS = "refresh_descriptions"

logger = logging.getLogger(__name__)


class ProposalService:
    """The only path an agent's change takes into a base (rule 5): a proposal, applied once accepted by the person,
    or on creation for an agent in auto mode, except a conflict or an input with no clear place."""

    def __init__(self, uow: UnitOfWork, storage: Storage) -> None:
        self._uow = uow
        self._pages = PageService(uow)
        self._tree = TreeService(uow)
        self._files = FileService(uow, storage)
        self._storage = storage

    async def listed(
        self,
        kb_id: UUID,
        status: Literal["pending", "applied"] = "pending",
        accepted_by: AcceptedBy | None = None,
        since: datetime | None = None,
    ) -> list[ProposalSummary]:
        """What waits for the person in the live base, newest first; or what was applied in it from `since` on,
        most recent first, so an agent's automatic changes can be undone."""
        await self._uow.kbs.get_in(kb_id)
        listed = await self._uow.proposals.listed(kb_id, status, accepted_by, since)
        conversations = {proposal.conversation_id for proposal in listed if proposal.conversation_id is not None}
        deleted = {id for id in conversations if (await self._uow.conversations.get(id)).deleted_at is not None}
        # A deleted conversation is not opened again: its proposal is shown as one with no conversation.
        gone = {"conversation_title": None}
        return [p.model_copy(update=gone) if p.conversation_id in deleted else p for p in listed]

    async def get(self, id: UUID) -> ProposalRead:
        return await self._uow.proposals.get(id)

    async def create(self, data: ProposalCreate, placed: bool = True) -> ProposalRead:
        """Stores the proposal, then `auto_accept`s it. An auto apply that fails leaves it pending for the person."""
        proposal = await self.add(data)
        await self._uow.commit()
        try:
            return await self.auto_accept(proposal, placed)
        except AcervoError:
            await self._uow.rollback()
            return await self._uow.proposals.get(proposal.id)

    async def add(self, data: ProposalCreate) -> ProposalRead:
        """Stores the proposal pending, in the caller's transaction."""
        agent = await self._uow.agents.get(data.agent_id)
        if agent.kb_id != data.kb_id:
            raise ValidationError("o agente não é desta base", {"agent_id": str(agent.id)})
        return await self._uow.proposals.create(data)

    async def auto_accept(self, proposal: ProposalRead, placed: bool = True) -> ProposalRead:
        """Applies a stored proposal when its agent is in auto mode, it is not a conflict and it has a clear place
        (`placed`); otherwise it stays pending. It is read again first: one the person accepted or rejected
        meanwhile is returned as it stands. A failing apply raises, and the caller rolls back."""
        proposal = await self._uow.proposals.get(proposal.id)
        agent = await self._uow.agents.get(proposal.agent_id)
        if proposal.status not in OPEN or agent.mode != "auto" or proposal.kind == "conflict" or not placed:
            return proposal
        return await self.accept(proposal.id, "auto")

    async def accept(self, id: UUID, by: AcceptedBy = "person") -> ProposalRead:
        """Applies the proposal, its edited version if any, in one transaction. Accepting an applied one changes
        nothing; one whose section or line is gone becomes `stale` and changes nothing."""
        proposal = await self._uow.proposals.locked(id)
        if proposal.status == "applied":
            return proposal
        self._open(proposal)
        try:
            await self._apply(proposal)
        except Stale:
            await self._uow.rollback()
            stale = await self._uow.proposals.update(id, ProposalUpdate(status="stale"))
            await self._uow.commit()
            return stale
        applied = await self._uow.proposals.update(
            id, ProposalUpdate(status="applied", accepted_by=by, applied_at=datetime.now(UTC))
        )
        await self._uow.commit()
        await self._discard(applied.staged)
        return applied

    async def reject(self, id: UUID, reason: RejectReason) -> ProposalRead:
        """The base stays as it was; a staged file is never saved into it."""
        self._open(await self._uow.proposals.locked(id))
        rejected = await self._uow.proposals.update(id, ProposalUpdate(status="rejected", reject_reason=reason))
        await self._uow.commit()
        await self._discard(rejected.staged)
        return rejected

    async def edit(self, id: UUID, payload: ProposalPayload) -> ProposalRead:
        """The person's version, applied in place of the original, which is kept."""
        proposal = await self._uow.proposals.locked(id)
        self._open(proposal)
        if payload.kind != proposal.kind:
            raise ValidationError("uma edição não muda o tipo da proposta", {"kind": payload.kind})
        edited = await self._uow.proposals.update(id, ProposalUpdate(edited_payload=payload, status="pending"))
        await self._uow.commit()
        return edited

    async def other_place(self, id: UUID) -> ProposalRead:
        """A new page or a file under the second place the Curator logged, without running it again."""
        proposal = await self._uow.proposals.locked(id)
        self._open(proposal)
        payload = proposal.edited_payload or proposal.payload
        if not proposal.alternatives or not isinstance(payload, CreatePagePayload | SavePdfPayload):
            raise ValidationError("não há outro lugar para esta proposta", {"id": str(id)})
        place = proposal.alternatives[0]
        moved = payload.model_copy(update={"parent_id": place.node_id, "parent_path": place.path})
        swapped = await self._uow.proposals.update(id, ProposalUpdate(edited_payload=moved))
        await self._uow.commit()
        return swapped

    async def undo(
        self,
        id: UUID,
        agent_id: UUID | None = None,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> ProposalRead:
        """A new `undo` proposal of an applied one, by `agent_id` or else by the agent that made it, in that agent's
        mode: a page back to its version before, a file back to its place or content before."""
        original = await self._uow.proposals.get(id)
        if original.status != "applied" or original.kind == "undo":
            raise ConflictError("só uma mudança aplicada pode ser desfeita", {"id": str(id)})
        path = await self._uow.nodes.path(await self._target(original))
        return await self.create(
            ProposalCreate(
                kb_id=original.kb_id,
                agent_id=agent_id or original.agent_id,
                conversation_id=conversation_id,
                message_id=message_id,
                payload=UndoPayload(proposal_id=original.id, path=path),
                undo_of=original.id,
            )
        )

    async def enqueue_refresh(self, jobs: JobQueue, proposal: ProposalRead) -> None:
        """The parents an applied proposal changed describe their children again, in the worker."""
        if proposal.status != "applied":
            return
        parents = [str(parent) for parent in dict.fromkeys(await self._changed_parents(proposal)) if parent]
        if parents:
            await jobs.enqueue(REFRESH_DESCRIPTIONS, node_ids=parents)

    async def _changed_parents(self, proposal: ProposalRead) -> list[UUID | None]:
        """The folders or pages that got, lost or renamed a child, whose descriptions follow their children."""
        payload = proposal.edited_payload or proposal.payload
        match payload:
            case CreatePagePayload() | SavePdfPayload():
                return [payload.parent_id]
            case MovePayload():
                return [payload.parent_id, payload.from_parent_id]
            case RenamePayload():
                return [(await self._uow.nodes.get(payload.node_id)).parent_id]
            case UndoPayload():
                return await self._changed_parents(await self._uow.proposals.get(payload.proposal_id))
            case _:
                return []

    async def _discard(self, staged: StagedFile | None) -> None:
        """A staged file no open proposal waits on any more is deleted: a saved one has its own copy in the base.
        The proposal is settled already, so a failed delete only leaves the file behind."""
        if staged is None or await self._uow.proposals.waits_on(staged.storage_key):
            return
        try:
            await self._storage.delete(staged.storage_key)
        except Exception:
            logger.exception("staged file %s was not deleted", staged.storage_key)

    def _open(self, proposal: ProposalRead) -> None:
        if proposal.status not in OPEN:
            raise ConflictError(f"a proposta já está {proposal.status}", {"status": proposal.status})

    async def _apply(self, proposal: ProposalRead) -> None:
        payload = proposal.edited_payload or proposal.payload
        match payload:
            case PatchPayload():
                change = Patch(payload.anchor, payload.op, payload.lines, payload.line)
                await self._patch(proposal, payload.page_id, change)
            case ConflictPayload():
                change = Patch(payload.anchor, "replace", payload.new.splitlines(), payload.current)
                await self._patch(proposal, payload.page_id, change)
            case CreatePagePayload():
                lines = payload.markdown.splitlines()
                markdown = patch.apply("", Patch("", "append", lines), await self._origin(proposal))
                page = NodeAdd(parent_id=payload.parent_id, kind="page", title=payload.title)
                await self._tree.create(proposal.kb_id, page, markdown=markdown, proposal_id=proposal.id, commit=False)
            case SavePdfPayload():
                async with self._download(proposal.staged) as source:
                    await self._files.save(proposal.kb_id, payload.parent_id, payload.name, source, commit=False)
            case ReplacePdfPayload():
                async with self._download(proposal.staged) as source:
                    await self._files.replace(payload.node_id, source, commit=False)
            case MovePayload():
                await self._tree.move(payload.node_id, NodeMove(parent_id=payload.parent_id), commit=False)
            case RenamePayload():
                await self._tree.rename(payload.node_id, payload.title, proposal_id=proposal.id, commit=False)
            case UndoPayload():
                await self._undo(proposal, await self._uow.proposals.get(payload.proposal_id))

    async def _patch(self, proposal: ProposalRead, page_id: UUID, change: Patch) -> None:
        origin = await self._origin(proposal)
        await self._pages.agent_write(page_id, lambda text: patch.apply(text, change, origin), proposal.id)

    async def _undo(self, proposal: ProposalRead, original: ProposalRead) -> None:
        """Changes back what `original` did; `Stale` when what it changed has changed again since."""
        node_id = await self._target(original)
        payload = original.edited_payload or original.payload
        match payload:
            case PatchPayload() | ConflictPayload():
                applied = await self._uow.page_versions.get_by(proposal_id=original.id)
                if applied is None:
                    raise NotFoundError(f"no version of proposal {original.id}", {"id": str(original.id)})
                before = await self._uow.page_versions.previous_markdown(applied)

                def back(text: str) -> str:
                    if text != applied.markdown:
                        raise Stale("the page changed after the proposal")
                    return before

                await self._pages.agent_write(node_id, back, proposal.id)
            case CreatePagePayload() | SavePdfPayload():
                await self._tree.trash(node_id, commit=False)
            case ReplacePdfPayload():
                current = await self._uow.files.of_node(node_id)
                history = await self._uow.file_versions.history(node_id)
                if original.staged is None or current.sha256 != original.staged.sha256 or not history:
                    raise Stale("the file changed after the proposal")
                await self._files.restore(node_id, history[0].id, commit=False)
            case MovePayload():
                if (await self._uow.nodes.live(node_id)).parent_id != payload.parent_id:
                    raise Stale("the node moved after the proposal")
                parent_id = await self._parent_at(original.kb_id, payload.from_path)
                await self._tree.move(node_id, NodeMove(parent_id=parent_id), commit=False)
            case RenamePayload():
                if (await self._uow.nodes.live(node_id)).title != payload.title:
                    raise Stale("the node was renamed after the proposal")
                title = payload.path.rsplit("/", 1)[-1]
                await self._tree.rename(node_id, title, proposal_id=proposal.id, commit=False)

    async def _target(self, proposal: ProposalRead) -> UUID:
        """The node an applied proposal changed."""
        payload = proposal.edited_payload or proposal.payload
        match payload:
            case PatchPayload() | ConflictPayload():
                return payload.page_id
            case CreatePagePayload():
                version = await self._uow.page_versions.get_by(proposal_id=proposal.id)
                if version is not None:
                    return version.node_id
            case SavePdfPayload():
                holder = (
                    None
                    if proposal.staged is None
                    else await self._uow.files.holder(proposal.kb_id, proposal.staged.sha256)
                )
                if holder is not None:
                    return holder.id
            case ReplacePdfPayload() | MovePayload() | RenamePayload():
                return payload.node_id
        raise NotFoundError(f"what proposal {proposal.id} changed is gone", {"id": str(proposal.id)})

    async def _parent_at(self, kb_id: UUID, path: str) -> UUID | None:
        """The live folder or page that held the node at `path`, walking titles from the root."""
        parent_id: UUID | None = None
        for title in path.split("/")[:-1]:
            children = await self._uow.nodes.children(kb_id, parent_id)
            parent = next((node for node in children if node.title == title and node.kind != "file"), None)
            if parent is None:
                raise Stale(f"{path} is gone")
            parent_id = parent.id
        return parent_id

    async def _origin(self, proposal: ProposalRead) -> str:
        agent = await self._uow.agents.get(proposal.agent_id)
        return patch.provenance("chat" if agent.built_in else agent.name, proposal.created_at.date(), proposal.id)

    @asynccontextmanager
    async def _download(self, staged: StagedFile | None) -> AsyncIterator[BinaryIO]:
        """The staged bytes from a local file, so the file service reads them as it reads an upload."""
        if staged is None:
            raise ValidationError("a proposta não tem arquivo", {})
        async with self._storage.download(staged.storage_key) as path:
            with path.open("rb") as source:
                yield source
