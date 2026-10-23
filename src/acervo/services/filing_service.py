"""The Curator as a service: a fact or a dropped PDF filed by the decisions of skill `curator-agent`, every decision
logged, its proposal stored pending. The chat's `file_fact` and `file_attachment`, an MCP agent's `remember` and
`save_file` and the evals all file through it."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.domain.cards import CardInput
from acervo.model_clients.decider import Decider
from acervo.model_clients.writer import Writer
from acervo.pipeline.curator import policy
from acervo.pipeline.curator.tree import PageText, SnapshotNode, TreeSnapshot
from acervo.pipeline.pdf import reader
from acervo.pipeline.search.previews import folder_description
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentRead
from acervo.schemas.conversation import Attachment
from acervo.schemas.node import NodeRead
from acervo.schemas.proposal import Decision, DecisionLogCreate, ProposalCreate, ProposalRead, StagedFile
from acervo.services.page_service import PageService
from acervo.services.proposal_service import ProposalService
from acervo.services.storage import Storage


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


class FilingService:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: Storage,
        decider: Decider,
        writer: Writer,
        thresholds: Thresholds,
        limits: RetrievalLimits | None = None,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._decider = decider
        self._writer = writer
        self._thresholds = thresholds
        self._chars = (limits or RetrievalLimits()).description_chars
        self._pages = PageService(uow)
        self._proposals = ProposalService(uow, storage)

    async def fact(self, text: str, origin: Origin) -> Filing:
        tree = await self._snapshot(origin.agent.kb_id)

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
        tree = await self._snapshot(origin.agent.kb_id)
        source = CardInput(text=text, file_name=attachment.name, outline=outline)
        staged = StagedFile(**attachment.model_dump(exclude={"mime"}))
        return await self._file(
            origin,
            lambda log: policy.file_pdf(source, tree, self._decider, self._writer, self._thresholds, log),
            staged,
        )

    async def _snapshot(self, kb_id: UUID) -> TreeSnapshot:
        """The base's live tree as the options show it: the person's descriptions, and what the index gives, the same
        built descriptions the search shows Jev."""
        nodes = await self._uow.nodes.live_in(kb_id)
        under: defaultdict[UUID | None, list[NodeRead]] = defaultdict(list)
        for node in nodes:
            under[node.parent_id].append(node)
        outlines = await self._uow.indexes.outlines([node.id for node in nodes if node.kind != "folder"])

        def built(node: NodeRead) -> str:
            if node.kind != "folder":
                return outlines.get(node.id, "")
            listed = [(child.title, outlines.get(child.id, "")) for child in under[node.id]]
            return folder_description(listed, self._chars)

        return TreeSnapshot(
            nodes=[
                SnapshotNode(
                    id=node.id,
                    parent_id=node.parent_id,
                    kind=node.kind,
                    title=node.title,
                    # A description an agent wrote is not kept.
                    description=node.description if node.description_locked else "",
                    built=built(node),
                    active_at=node.updated_at,
                )
                for node in nodes
            ]
        )

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
