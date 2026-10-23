"""Search by descent: Jev routes down the tree in a beam and scores the passages of each section it reaches (skill
`navigator-agent`). Pure computation over the tree the caller hands in; nothing is read from or written to the base.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from acervo.core.settings import RetrievalLimits, Thresholds
from acervo.domain.decisions import Answers
from acervo.domain.index import Evidence, Passage, SearchResult, SearchStage, SearchStep
from acervo.model_clients.decider import Decider
from acervo.pipeline.curator.log import record
from acervo.pipeline.search import questions
from acervo.pipeline.search.menus import bounded, menu, packs
from acervo.pipeline.search.tree import SearchKind, SearchNode
from acervo.schemas.proposal import Decision

OnStep = Callable[[SearchStep], Awaitable[None]]

# From this many partial passages on, one Score asks whether together they answer the question.
SET_CHECK = 3
# A chosen route never scores 0: its log stays finite and it can still be reached when the beam runs dry.
FLOOR = 1e-6
_STAGE: dict[SearchKind, SearchStage] = {
    "folder": "folder",
    "page": "document",
    "file": "document",
    "section": "section",
    "stats": "section",
}


@dataclass(frozen=True)
class Route:
    node: SearchNode
    log_probability: float = 0.0
    # Menus of more than one option on the way; a single child is no decision and does not count.
    decisions: int = 0

    @property
    def score(self) -> float:
        """The geometric mean of the chosen options' probabilities: ranks routes, never shown as a confidence."""
        return math.exp(self.log_probability / self.decisions) if self.decisions else 1.0

    def extend(self, node: SearchNode, probability: float | None) -> "Route":
        if probability is None:
            return Route(node, self.log_probability, self.decisions)
        return Route(node, self.log_probability + math.log(max(probability, FLOOR)), self.decisions + 1)


@dataclass
class _Candidate:
    node: SearchNode
    passage: Passage
    route_score: float


def _evidence_text(node: SearchNode, passage: Passage) -> str:
    head = [f"Fonte: {'/'.join(node.path)}", f"Seção: {node.title}"]
    if passage.page is not None:
        head.append(f"Páginas: {passage.page}–{passage.end_page or passage.page}")
    return "\n".join(head) + f"\n\n{passage.text}"


class _Search:
    def __init__(
        self,
        query: str,
        roots: list[SearchNode],
        decider: Decider,
        limits: RetrievalLimits,
        thresholds: Thresholds,
        on_step: OnStep | None,
    ) -> None:
        self.query, self.decider, self.limits, self.thresholds, self.on_step = (
            query,
            decider,
            limits,
            thresholds,
            on_step,
        )
        top = SearchNode(id="root", node_id=None, kind="group", title="Base", path=[], loaded=roots)
        self.beam = [Route(top)]
        # Routes past the beam, ranked again at every level; routes "none" beat, taken only when a walk starts over.
        self.waiting: list[Route] = []
        self.deferred: list[Route] = []
        self.visited: set[str] = set()
        self.expanded: set[str] = set()
        self.evidence_visits: Counter[UUID | None] = Counter()
        self.expansions = 0
        self.decisions: list[Decision] = []
        self.trace: list[SearchStep] = []
        self.looked_in: list[str] = []

    def rank(self, route: Route) -> tuple[int, float]:
        """After `sections_per_document` sections of one document, routes into others come first."""
        node_id = route.node.node_id
        rounds = self.evidence_visits[node_id] // self.limits.sections_per_document if node_id else 0
        return rounds, -route.score

    @property
    def exhausted(self) -> bool:
        return self.expansions >= self.limits.expansions or not (self.beam or self.waiting or self.deferred)

    async def walk(self) -> list[Route]:
        """Down from the beam until a level reaches nodes with passages; returns the routes reached on the way."""
        found: list[Route] = []
        ranked = sorted(self.beam + self.waiting + self.deferred, key=self.rank)
        self.beam, self.waiting, self.deferred = ranked[: self.limits.beam], ranked[self.limits.beam :], []
        while self.beam and self.expansions < self.limits.expansions:
            evidence = False
            for route in self.beam:
                if route.node.id not in self.visited:
                    self.visited.add(route.node.id)
                    found.append(route)
                    if route.node.passages():
                        evidence = True
                        self.evidence_visits[route.node.node_id] += 1
            if evidence:
                return found
            opened: list[tuple[Route, list[SearchNode]]] = []
            for route in self.beam:
                if route.node.id in self.expanded or self.expansions >= self.limits.expansions:
                    continue
                self.expanded.add(route.node.id)
                children = await route.node.children()
                if children:
                    self.expansions += 1
                    bound = bounded(children, route.node.id, self.limits.menu, self.limits.description_chars)
                    opened.append((route, bound))
            if not opened:
                break
            answers = await self.route(opened)
            expanded: list[Route] = []
            for route, children in opened:
                id = f"route:{route.node.id}"
                if id not in answers:
                    expanded += [route.extend(child, None) for child in children]
                    continue
                *probs, none = answers[id].probs[id]
                for child, probability in zip(children, probs, strict=True):
                    rejected = probability <= 0 or probability < none
                    (self.deferred if rejected else expanded).append(route.extend(child, probability))
            waiting = [route for route in self.waiting if route.node.id not in self.expanded]
            ranked = sorted(expanded + waiting, key=self.rank)
            self.beam = ranked[: self.limits.beam]
            self.waiting = ranked[self.limits.beam :][: self.limits.expansions]
            self.deferred = self.deferred[: self.limits.expansions]
            kept = " | ".join("/".join(route.node.path) or route.node.title for route in self.beam)
            for id, by in answers.items():
                self.decisions.append(record(by, id, "route", f"kept {kept}"))
        self.beam = []
        return found

    async def route(self, opened: list[tuple[Route, list[SearchNode]]]) -> dict[str, Answers]:
        """One menu per opened node with more than one child, `menus_per_call` menus to a Jev call."""
        menus = [
            menu(f"route:{route.node.id}", children, self.query, self.limits.description_chars)
            for route, children in opened
            if len(children) > 1
        ]
        by_id: dict[str, Answers] = {}
        for pack in packs(menus, self.limits.menus_per_call):
            answers = await self.decider.ask(self.query, pack)
            by_id |= {choice.id: answers for choice in pack}
        return by_id

    async def step(self, stage: SearchStage, label: str, node_id: UUID, page: int | None = None) -> None:
        step = SearchStep(stage=stage, label=label, node_id=node_id, page=page)
        self.trace.append(step)
        if self.on_step:
            await self.on_step(step)

    async def reached(self, node: SearchNode) -> None:
        if node.node_id is None or node.kind == "group":
            return
        if node.kind in ("folder", "page", "file") and (where := "/".join(node.path)) not in self.looked_in:
            self.looked_in.append(where)
        await self.step(_STAGE[node.kind], node.title, node.node_id, node.page)

    async def score(self, batch: list[_Candidate]) -> list[Evidence]:
        """One Score per passage, all in one call; those under `evidence_min` are dropped."""
        for candidate in batch:
            assert candidate.node.node_id is not None
            await self.step("passage", candidate.node.title, candidate.node.node_id, candidate.passage.page)
        scores = [questions.usefulness(f"evidence:{i}", _evidence_text(c.node, c.passage)) for i, c in enumerate(batch)]
        answers = await self.decider.ask(self.query, scores)
        kept: list[Evidence] = []
        for question, candidate in zip(scores, batch, strict=True):
            score = answers.score(question.id)
            keep = score >= self.thresholds.evidence_min
            self.decisions.append(
                record(answers, question.id, "evidence", "kept" if keep else "dropped", self.thresholds.evidence_min)
            )
            if keep:
                node, passage = candidate.node, candidate.passage
                assert node.node_id is not None
                kept.append(
                    Evidence(
                        ref=f"{node.node_id}:{passage.id}",
                        node_id=node.node_id,
                        path=node.path,
                        section_title=node.title,
                        page=passage.page,
                        end_page=passage.end_page,
                        text=passage.text,
                        block_ids=passage.block_ids,
                        score=score,
                        route_score=candidate.route_score,
                    )
                )
        return kept

    async def covers(self, evidence: Sequence[Evidence]) -> bool:
        """Whether the partial passages together answer: one Score over all of them."""
        joined = "\n\n".join(f"Fonte: {'/'.join(e.path)}\nSeção: {e.section_title}\n{e.text}" for e in evidence)
        question = questions.usefulness("evidence_set", joined[: self.limits.result_chars])
        answers = await self.decider.ask(self.query, [question])
        threshold = self.thresholds.evidence_enough
        enough = answers.score(question.id) >= threshold
        self.decisions.append(record(answers, question.id, "evidence_set", "enough" if enough else "short", threshold))
        return enough

    def ranked(self, results: list[Evidence]) -> list[Evidence]:
        """By score, then route score, within `results` passages and `result_chars` characters."""
        out: list[Evidence] = []
        chars = 0
        for evidence in sorted(results, key=lambda e: (-e.score, -e.route_score)):
            if len(out) >= self.limits.results:
                break
            if chars + len(evidence.text) <= self.limits.result_chars:
                out.append(evidence)
                chars += len(evidence.text)
        return out

    async def run(self) -> SearchResult:
        candidates: list[_Candidate] = []
        results: list[Evidence] = []
        sections: defaultdict[UUID | None, set[str]] = defaultdict(set)
        scored = 0
        checked: list[str] = []

        def rounds(candidate: _Candidate) -> int:
            others = sections[candidate.node.node_id] - {candidate.node.id}
            return len(others) // self.limits.sections_per_document

        while (not self.exhausted or candidates) and scored < self.limits.passages:
            for route in [] if self.exhausted else await self.walk():
                await self.reached(route.node)
                candidates += [_Candidate(route.node, p, route.score) for p in route.node.passages()]
            batch: list[_Candidate] = []
            while candidates and len(batch) < min(self.limits.per_score_call, self.limits.passages - scored):
                candidates.sort(key=lambda c: (rounds(c), -c.route_score))
                batch.append(chosen := candidates.pop(0))
                sections[chosen.node.node_id].add(chosen.node.id)
            if not batch:
                continue
            scored += len(batch)
            results += await self.score(batch)
            if any(e.score >= self.thresholds.evidence_enough for e in results):
                break
            if len(results) >= SET_CHECK:
                top = self.ranked(results)
                if [e.ref for e in top] != checked:
                    checked = [e.ref for e in top]
                    if await self.covers(top):
                        break
        return SearchResult(evidence=self.ranked(results), trace=self.trace, looked_in=self.looked_in)


async def search(
    query: str,
    roots: list[SearchNode],
    decider: Decider,
    limits: RetrievalLimits,
    thresholds: Thresholds,
    on_step: OnStep | None = None,
) -> tuple[SearchResult, list[Decision]]:
    """Every Jev call's decisions come back for the log. An invalid answer from the decider propagates: there is no
    fallback to another way of searching."""
    run = _Search(query, roots, decider, limits, thresholds, on_step)
    return await run.run(), run.decisions
