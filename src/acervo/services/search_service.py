"""Search as a service: the base's live tree handed to the engine, a document's index read only when the search
opens it, every Jev call logged with the run (skill `navigator-agent`). The chat's search and an MCP agent's both
come through here."""

from collections import defaultdict
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.domain.index import DocIndex, Evidence, Passage, SearchStep, Section
from acervo.model_clients.decider import Decider
from acervo.pipeline.index.stats import term_count
from acervo.pipeline.search import engine
from acervo.pipeline.search.candidates import candidate_branch
from acervo.pipeline.search.previews import folder_description, section_previews, terms
from acervo.pipeline.search.tree import SearchNode, stats_node
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeRead
from acervo.schemas.proposal import Decision, DecisionLogCreate


class Cited(Evidence):
    """A passage the search kept, with where a citation of it points: the first of its blocks."""

    kind: Literal["page", "file"] = Field(description="A page, or a PDF.")
    anchor: str | None = Field(description="The page's section; null for a PDF or the text before the first one.")
    block_id: str | None = Field(description="The first block of the passage in its index.")
    highlight: tuple[float, float, float, float] | None = Field(
        description="That block's box on its PDF page, in points (x0, y0, x1, y1); null for a page."
    )


class Searched(BaseModel):
    evidence: list[Cited] = Field(description="Best first, within the result limits.")
    trace: list[SearchStep] = Field(description="Where the search went, in order.")
    looked_in: list[str] = Field(description="The folders and documents it reached, for an answer of not found.")


class SearchService:
    def __init__(self, uow: UnitOfWork, decider: Decider, limits: RetrievalLimits, thresholds: Thresholds) -> None:
        self._uow = uow
        self._decider = decider
        self._limits = limits
        self._thresholds = thresholds

    async def search(
        self,
        kb_id: UUID,
        query: str,
        *,
        run_id: UUID,
        message_id: UUID | None = None,
        on_step: engine.OnStep | None = None,
    ) -> Searched:
        """An invalid answer from the decider propagates: there is no other way of searching to fall back to."""
        nodes = await self._uow.nodes.live_in(kb_id)
        under: defaultdict[UUID | None, list[NodeRead]] = defaultdict(list)
        for node in nodes:
            under[node.parent_id].append(node)
        outlines = await self._uow.indexes.outlines([node.id for node in nodes if node.kind != "folder"])
        indexes: dict[UUID, DocIndex] = {}
        documents: list[SearchNode] = []
        chars = self._limits.description_chars

        def build(node: NodeRead, above: list[str]) -> SearchNode:
            path = [*above, node.title]
            children = [build(child, path) for child in under[node.id]]
            # A description an agent wrote is not kept: what Jev sees is built from the index.
            person = node.description if node.description_locked else ""
            if node.kind == "folder":
                listed = [(child.title, outlines.get(child.id, "")) for child in under[node.id]]
                return SearchNode(
                    id=str(node.id),
                    node_id=node.id,
                    kind="folder",
                    title=node.title,
                    path=path,
                    person_description=person,
                    built=folder_description(listed, chars),
                    loaded=children,
                )

            async def load() -> list[SearchNode]:
                return [*await self._sections(node.id, path, query, indexes), *children]

            document = SearchNode(
                id=str(node.id),
                node_id=node.id,
                kind=node.kind,
                title=node.title,
                path=path,
                person_description=person,
                built=outlines.get(node.id, ""),
                load=load,
            )
            documents.append(document)
            return document

        roots = [build(node, []) for node in under[None]]
        if branch := candidate_branch(documents, query, chars, self._limits.candidates):
            roots.insert(0, branch)
        decisions: list[Decision] = []
        try:
            result, _ = await engine.search(
                query, roots, self._decider, self._limits, self._thresholds, on_step, decisions
            )
        finally:
            await self._uow.decisions.create_many(
                [DecisionLogCreate(run_id=run_id, message_id=message_id, **d.model_dump()) for d in decisions]
            )
            await self._uow.commit()
        kinds = {node.id: node.kind for node in nodes}
        return Searched(
            evidence=[_cited(found, kinds[found.node_id], indexes[found.node_id]) for found in result.evidence],
            trace=result.trace,
            looked_in=result.looked_in,
        )

    async def _sections(
        self, node_id: UUID, path: list[str], query: str, indexes: dict[UUID, DocIndex]
    ) -> list[SearchNode]:
        """A document's sections and its statistics branch; nothing for one not indexed yet."""
        if node_id not in indexes:
            found = await self._uow.indexes.get(node_id)
            if found is None or found.parsed is None:
                return []
            indexes[node_id] = found.parsed
        index = indexes[node_id]
        previews = section_previews(index, query, self._limits.description_chars)
        passages: defaultdict[str, list[Passage]] = defaultdict(list)
        for passage in index.passages:
            passages[passage.section_id].append(passage)

        def section(found: Section) -> SearchNode:
            return SearchNode(
                id=f"{node_id}:{found.id}",
                node_id=node_id,
                kind="section",
                title=found.title,
                path=path,
                built=previews.get(found.id, ""),
                page=found.page,
                end_page=found.end_page,
                passage_list=passages[found.id],
                loaded=[section(child) for child in found.children],
            )

        counts = {term: term_count(index, term) for term in dict.fromkeys(terms(query))}
        # A PDF read by its name only has no counts to give: "0 tabelas" would be a wrong answer, not a count.
        stats = [] if index.note else [stats_node(node_id, path, index.stats, counts)]
        return [*map(section, index.sections), *stats]


def _cited(evidence: Evidence, kind: Literal["folder", "page", "file"], index: DocIndex) -> Cited:
    assert kind != "folder"
    passage_id = evidence.ref.partition(":")[2]
    # The statistics branch's passage is no passage of the index: it cites the document.
    passage = next((passage for passage in index.passages if passage.id == passage_id), None)
    first = next((block for block in index.blocks if evidence.block_ids and block.id == evidence.block_ids[0]), None)
    return Cited(
        **evidence.model_dump(),
        kind=kind,
        anchor=(passage.section_id or None) if passage and kind == "page" else None,
        block_id=first.id if first else None,
        highlight=first.bbox if first else None,
    )
