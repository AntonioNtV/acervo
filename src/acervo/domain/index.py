"""The structural index of a PDF or a page, and what a search returns (skills `pdf-files`, `navigator-agent`)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

BlockKind = Literal["paragraph", "heading", "table", "figure", "list"]
SearchStage = Literal["folder", "document", "section", "passage"]


class Block(BaseModel):
    """The smallest unit a citation points at; a page's blocks have no page or position."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: BlockKind
    text: str
    page: int | None = None
    # PDF points on `page`: x0, y0, x1, y1.
    bbox: tuple[float, float, float, float] | None = None
    page_size: tuple[float, float] | None = None


class Section(BaseModel):
    """A heading and what follows it until the next one of its level, across PDF pages."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    level: int
    page: int | None = None
    end_page: int | None = None
    block_ids: list[str] = []
    children: list["Section"] = []


class Passage(BaseModel):
    """An evidence unit of one section that Jev scores; never retrieved by similarity (rule 4 of CLAUDE.md)."""

    model_config = ConfigDict(frozen=True)

    id: str
    section_id: str
    text: str
    page: int | None = None
    end_page: int | None = None
    block_ids: list[str] = []


class DocStats(BaseModel):
    """Counts over the whole document, so "how many" is answered from counts, never from samples."""

    model_config = ConfigDict(frozen=True)

    pages: int
    words: int
    tables: int
    figures: int


class DocIndex(BaseModel):
    """The index of one version of a PDF or a page. Kept for search only; never content of the base."""

    model_config = ConfigDict(frozen=True)

    version: int
    source: Literal["pdf", "markdown"]
    outline: str
    sections: list[Section]
    blocks: list[Block]
    passages: list[Passage]
    stats: DocStats
    # Set when a PDF has a password or no text: it is indexed by name and outline only.
    note: str | None = None


class Evidence(BaseModel):
    """A scored passage a search returns, with where it is."""

    model_config = ConfigDict(frozen=True)

    ref: str
    node_id: UUID
    path: list[str]
    section_title: str
    page: int | None
    end_page: int | None
    text: str
    block_ids: list[str]
    # Jev's usefulness, 0 to 3.
    score: float
    # Ranks routes only; never shown as a confidence.
    route_score: float


class SearchStep(BaseModel):
    """Where a search went, for the reply's activity line and for "where I looked"."""

    model_config = ConfigDict(frozen=True)

    stage: SearchStage
    label: str
    node_id: UUID
    page: int | None = None


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: list[Evidence]
    trace: list[SearchStep]
    looked_in: list[str]
