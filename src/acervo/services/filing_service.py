"""The Curator as a service: a fact or a dropped PDF filed by the decisions of skill `curator-agent`, every decision
logged, its proposal stored pending. The chat's `file_fact` and `file_attachment`, an MCP agent's `remember` and
`save_file` and the evals all file through it."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from acervo.core.errors import NotFoundError
from acervo.core.settings import Thresholds
from acervo.domain.cards import CardInput, ChildDescription
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.pipeline.curator import policy
from acervo.pipeline.curator.tree import PageText, SnapshotNode, TreeSnapshot
from acervo.pipeline.pdf import reader
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead
from acervo.schemas.conversation import Attachment
from acervo.schemas.node import NodeUpdate
from acervo.schemas.proposal import Decision, DecisionLogCreate, ProposalCreate, ProposalRead, StagedFile
from acervo.services.page_service import PageService
from acervo.services.proposal_service import ProposalService
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService

# How many descriptions are written at once when a tree is described before filing.
DESCRIBING = 4


@dataclass(frozen=True)
class Origin:
    """Who files, and the run and reply its decisions and proposals are linked to."""

    agent: AgentRead
    run_id: UUID
    conversation_id: UUID | None = None
    message_id: UUID | None = None


class Filing(BaseModel):
    """What one input became: a pending proposal, placed or waiting in "Sem lugar definido" (`placed` false), or
    nothing because it is already written."""

    proposal: ProposalRead | None = None
    placed: bool = True
    written: policy.AlreadyWritten | None = None


def _depth(tree: TreeSnapshot, node: SnapshotNode) -> int:
    depth = 0
    while node.parent_id is not None:
        node, depth = tree.node(node.parent_id), depth + 1
    return depth


class FilingService:
    def __init__(
        self, uow: UnitOfWork, storage: Storage, decider: Decider, writer: Writer, thresholds: Thresholds
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._decider = decider
        self._writer = writer
        self._thresholds = thresholds
        self._pages = PageService(uow)
        self._tree = TreeService(uow)
        self._proposals = ProposalService(uow, storage)

    async def fact(self, text: str, origin: Origin) -> Filing:
        tree = await self.described(origin.agent.kb_id)

        async def read_page(node_id: UUID) -> PageText:
            # What the person sees is what the Curator reads.
            await self._pages.cut(node_id)
            version = await self._uow.page_versions.current(node_id)
            return PageText(page_id=node_id, version_id=version.id, markdown=version.markdown)

        source = CardInput(text=text)
        return await self._file(
            origin,
            lambda log: policy.file_text(source, tree, read_page, self._decider, self._writer, self._thresholds, log),
        )

    async def attachment(self, attachment: Attachment, origin: Origin) -> Filing:
        """A staged PDF, read from its first pages and outline only."""
        async with self._storage.download(attachment.storage_key) as path:
            text, outline = await asyncio.to_thread(reader.first_pages, path)
        tree = await self.described(origin.agent.kb_id)
        source = CardInput(text=text, file_name=attachment.name, outline=outline)
        staged = StagedFile(**attachment.model_dump(exclude={"mime"}))
        return await self._file(
            origin,
            lambda log: policy.file_pdf(source, tree, self._decider, self._writer, self._thresholds, log),
            staged,
        )

    async def described(self, kb_id: UUID) -> TreeSnapshot:
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

    async def _file(
        self,
        origin: Origin,
        decide: Callable[[list[Decision]], Awaitable[policy.Filed]],
        staged: StagedFile | None = None,
    ) -> Filing:
        """The decisions and the pending proposal in one transaction; on a failure, the decisions asked so far are
        logged, and nothing else is left."""
        log: list[Decision] = []
        try:
            filed = await decide(log)
        except BaseException:
            await self._uow.rollback()
            await self._log(origin, log)
            await self._uow.commit()
            raise
        await self._log(origin, log)
        if isinstance(filed, policy.AlreadyWritten):
            await self._uow.commit()
            return Filing(written=filed)
        # A filing's NotSure always carries what waits in "Sem lugar definido".
        assert filed.payload is not None
        alternatives = filed.alternatives if isinstance(filed, policy.Propose) else filed.options
        proposal = await self._proposals.add(
            ProposalCreate(
                kb_id=origin.agent.kb_id,
                agent_id=origin.agent.id,
                conversation_id=origin.conversation_id,
                message_id=origin.message_id,
                run_id=origin.run_id,
                payload=filed.payload,
                alternatives=alternatives or None,
                staged=staged,
            )
        )
        await self._uow.commit()
        return Filing(proposal=proposal, placed=isinstance(filed, policy.Propose))

    async def _log(self, origin: Origin, log: list[Decision]) -> None:
        await self._uow.decisions.create_many(
            [
                DecisionLogCreate(run_id=origin.run_id, message_id=origin.message_id, **decision.model_dump())
                for decision in log
            ]
        )

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
