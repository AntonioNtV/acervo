"""The tree a search descends, as the caller hands it over: children load only when the search opens a node."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from acervo.domain.index import DocStats, Passage

# "group": a set of siblings a menu too long was cut into, or the shortcut's branch; it is not a node of the base.
SearchKind = Literal["folder", "page", "file", "section", "stats", "group"]


@dataclass(eq=False)
class SearchNode:
    id: str
    # The base's node it is or belongs to (a section's document); None for a group.
    node_id: UUID | None
    kind: SearchKind
    title: str
    # Titles from the base's root down to that node.
    path: list[str]
    person_description: str = ""
    # What the index says of it: an outline, or a section's preview built for the question.
    built: str | Callable[[str], str] = ""
    page: int | None = None
    end_page: int | None = None
    load: Callable[[], Awaitable[list["SearchNode"]]] | None = None
    passage_list: list[Passage] = field(default_factory=list)
    # The children, once known: given up front, or loaded the first time they are asked for.
    loaded: list["SearchNode"] | None = field(default=None, repr=False)

    def describe(self, query: str) -> str:
        """What Jev sees of it as an option; a description the person wrote comes before the built one."""
        built = self.built(query) if callable(self.built) else self.built
        return "\n".join(part for part in (self.title, self.person_description, built) if part)

    async def children(self) -> list["SearchNode"]:
        if self.loaded is None:
            self.loaded = await self.load() if self.load else []
        return self.loaded

    def passages(self) -> list[Passage]:
        return self.passage_list


def stats_node(node_id: UUID, path: list[str], stats: DocStats, term_counts: Mapping[str, int]) -> SearchNode:
    """A document's statistics branch: "how many" is answered from counts over the whole document, never samples."""
    terms = "; ".join(f'"{term}": {count}' for term, count in term_counts.items())
    text = (
        f"Contagens do documento inteiro, não amostras: {stats.pages} páginas, {stats.words} palavras, "
        f"{stats.tables} tabelas, {stats.figures} figuras."
        + (f" Ocorrências de termos da pergunta: {terms}." if terms else "")
    )
    return SearchNode(
        id=f"stats:{node_id}",
        node_id=node_id,
        kind="stats",
        title="Estatísticas do documento",
        path=path,
        built="Páginas, palavras, tabelas, figuras e ocorrências de termos, contadas no documento inteiro.",
        page=1 if stats.pages else None,
        end_page=stats.pages or None,
        passage_list=[
            Passage(
                id="stats", section_id="stats", text=text, page=1 if stats.pages else None, end_page=stats.pages or None
            )
        ],
    )
