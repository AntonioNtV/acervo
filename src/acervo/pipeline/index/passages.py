"""Cutting a section's blocks into the passages Jev scores, and assembling a `DocIndex` (skill `pdf-files`)."""

from dataclasses import dataclass
from typing import Literal

from acervo.core.settings import RetrievalLimits
from acervo.domain.index import Block, DocIndex, DocStats, Passage, Section

# The shape of `DocIndex`; after a bump, run `make reindex` on every base.
VERSION = 1


@dataclass(frozen=True)
class Start:
    """Where a section starts, before sections are nested: its blocks are its own, not its children's."""

    id: str
    title: str
    level: int
    page: int | None
    blocks: list[Block]


def split(section_id: str, blocks: list[Block], limits: RetrievalLimits) -> list[Passage]:
    """Passages of at most `passage_chars`, the next repeating the last `passage_overlap` of text; a table is cut
    between rows, never inside one, and every passage holding its rows starts them with the header."""
    size, overlap = limits.passage_chars, limits.passage_overlap
    passages: list[Passage] = []
    text, used, table = "", list[Block](), ""

    def emit() -> None:
        pages = [block.page for block in used if block.page is not None]
        passages.append(
            Passage(
                id=f"{section_id}-p{len(passages) + 1}",
                section_id=section_id,
                text=text,
                page=min(pages, default=None),
                end_page=max(pages, default=None),
                block_ids=list(dict.fromkeys(block.id for block in used)),
            )
        )

    for block, piece, header in _units(blocks, size - overlap):
        continues = bool(header) and table == header
        addition = piece if continues or not header else f"{header}\n{piece}"
        if text and len(text) + 2 + len(addition) > size:
            emit()
            # The overlap carries text only: a table's next passage repeats its header instead.
            tail = "" if table or not overlap else text[-overlap:].partition(" ")[2]
            text, used, table, continues = tail, used[-1:] if tail else [], "", False
            addition = f"{header}\n{piece}" if header else piece
            if text and len(text) + 2 + len(addition) > size:
                text, used = "", []
        separator = "\n" if continues else "\n\n"
        text = f"{text}{separator}{addition}" if text else addition
        used.append(block)
        table = header
    if text:
        emit()
    return passages


def _units(blocks: list[Block], window: int) -> list[tuple[Block, str, str]]:
    """Each block as (block, text, table header): a table row by row, a text longer than `window` in windows."""
    units: list[tuple[Block, str, str]] = []
    for block in blocks:
        if block.kind == "table":
            lines = block.text.split("\n")
            header = "\n".join(lines[:2])
            units += [(block, row, header) for row in lines[2:]] or [(block, header, "")]
        elif block.text.strip():
            units += [(block, piece, "") for piece in _windows(block.text, window)]
    return units


def _windows(text: str, size: int) -> list[str]:
    pieces: list[str] = []
    while len(text) > size:
        cut = text.rfind(" ", size // 2, size)
        cut = cut + 1 if cut > 0 else size
        pieces.append(text[:cut])
        text = text[cut:]
    return [*pieces, text] if text else pieces


def assemble(
    source: Literal["pdf", "markdown"],
    starts: list[Start],
    blocks: list[Block],
    pages: int | None,
    limits: RetrievalLimits,
    stats: DocStats,
) -> DocIndex:
    """Nests the starts by level, a section ending where the next one of its level or above begins (`pages` is the
    PDF's page count, None for a Markdown page), and cuts each one's passages."""
    passages: list[Passage] = []

    def nest(at: int, parent_level: int) -> tuple[list[Section], int]:
        found: list[Section] = []
        while at < len(starts) and starts[at].level > parent_level:
            start = starts[at]
            passages.extend(split(start.id, start.blocks, limits))
            children, after = nest(at + 1, start.level)
            end_page = None
            if pages is not None and start.page is not None:
                boundary = starts[after].page if after < len(starts) else None
                ends = [block.page for block in start.blocks if block.page is not None]
                ends += [child.end_page for child in children if child.end_page is not None]
                end_page = max([start.page, (boundary or pages + 1) - 1, *ends])
            found.append(
                Section(
                    id=start.id,
                    title=start.title,
                    level=start.level,
                    page=start.page,
                    end_page=end_page,
                    block_ids=[block.id for block in start.blocks],
                    children=children,
                )
            )
            at = after
        return found, at

    sections, _ = nest(0, min((start.level for start in starts), default=1) - 1)
    outline = "; ".join(start.title for start in starts)[: limits.description_chars]
    return DocIndex(
        version=VERSION,
        source=source,
        outline=outline,
        sections=sections,
        blocks=blocks,
        passages=passages,
        stats=stats,
    )
