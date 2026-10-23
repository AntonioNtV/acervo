"""A PDF's index, read with PyMuPDF: sections from bookmarks, else big headings, else one per page (skill
`pdf-files`). The text is kept for search only; the PDF never becomes a page (rule 3 of CLAUDE.md)."""

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf

from acervo.core.settings import RetrievalLimits
from acervo.domain.index import Block, BlockKind, DocIndex, DocStats
from acervo.pipeline.index.passages import VERSION, Start, assemble
from acervo.pipeline.index.stats import doc_stats, tokens

_LIST = re.compile(r"^\s*([•·▪‣◦*\-–]|\d+[.)])\s")
_BOLD = 16
# A heading is a short line, bold or this much bigger than the body text.
_HEADING_SCALE = 1.2
_HEADING_CHARS = 120

PROTECTED = "PDF protegido por senha: indexado só pelo nome e pelo sumário."
BROKEN = "PDF ilegível: indexado só pelo nome."
NO_TEXT = "PDF sem texto extraível: indexado só pelo nome e pelo sumário."


def index_pdf(path: Path, limits: RetrievalLimits) -> DocIndex:
    try:
        document = pymupdf.open(path, filetype="pdf")  # type: ignore[no-untyped-call]
    except (pymupdf.FileDataError, RuntimeError):
        return _outline_only([], 0, BROKEN, limits)
    with document:
        if document.needs_pass:
            return _outline_only([], document.page_count, PROTECTED, limits)
        toc = [(level, title.strip(), page) for level, title, page, *_ in document.get_toc() if page >= 1]
        pages = [_page(document[number]) for number in range(document.page_count)]
    body = _body_size(pages)
    blocks: list[Block] = []
    sizes: dict[str, float] = {}
    continued = 0
    for number, raw in enumerate(pages, start=1):
        for at, (kind, text, bbox, size, bold, size_of_page) in enumerate(raw):
            block = Block(
                id=f"p{number}-b{at + 1}",
                kind=kind if kind != "paragraph" else _kind(text, size, bold, body),
                text=text,
                page=number,
                bbox=bbox,
                page_size=size_of_page,
            )
            if block.kind == "table" and at == 0 and blocks and blocks[-1].kind == "table":
                block, joined = _continue(blocks[-1], block)
                continued += joined
            if block.kind == "heading":
                sizes[block.id] = size
            blocks.append(block)
    if not any(block.text.strip() for block in blocks):
        return _outline_only([title for _, title, _ in toc], len(pages), NO_TEXT, limits)
    starts = _by_bookmarks(toc, blocks) or _by_headings(blocks, sizes) or _by_page(blocks, len(pages))
    return assemble("pdf", starts, blocks, len(pages), limits, doc_stats(len(pages), blocks, continued))


_Raw = tuple[BlockKind, str, tuple[float, float, float, float], float, bool, tuple[float, float]]


def _page(page: pymupdf.Page) -> list[_Raw]:
    """The page's blocks in reading order: text with its biggest font size and whether all of it is bold, tables
    as Markdown, images as figures without text."""
    size = (page.rect.width, page.rect.height)
    # The default table finder follows ruling lines, so a page without drawings has no table to find.
    tables = page.find_tables().tables if page.get_drawings() else []  # type: ignore[no-untyped-call]
    found: list[_Raw] = [("table", _markdown(table.extract()), tuple(table.bbox), 0.0, False, size) for table in tables]
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    for raw in page.get_text("dict", flags=flags, sort=True)["blocks"]:  # type: ignore[no-untyped-call]
        spans = [span for line in raw["lines"] for span in line["spans"] if span["text"].strip()]
        x0, y0, x1, y1 = raw["bbox"]
        if not spans or any(_inside(((x0 + x1) / 2, (y0 + y1) / 2), table.bbox) for table in tables):
            continue
        text = " ".join(" ".join("".join(span["text"] for span in line["spans"]) for line in raw["lines"]).split())
        biggest = max(span["size"] for span in spans)
        bold = all(span["flags"] & _BOLD for span in spans) and len(raw["lines"]) <= 2
        found.append(("paragraph", text, tuple(raw["bbox"]), biggest, bold, size))
    found += [("figure", "", tuple(image["bbox"]), 0.0, False, size) for image in page.get_image_info()]
    return sorted(found, key=lambda block: (block[2][1], block[2][0]))


def _inside(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _body_size(pages: list[list[_Raw]]) -> float:
    """The font size most of the text is written in."""
    counts = Counter[float]()
    for raw in pages:
        for kind, text, _, size, _, _ in raw:
            if kind == "paragraph":
                counts[round(size, 1)] += len(text)
    return counts.most_common(1)[0][0] if counts else 0.0


def _kind(text: str, size: float, bold: bool, body: float) -> BlockKind:
    if len(text) <= _HEADING_CHARS and (bold or size >= body * _HEADING_SCALE):
        return "heading"
    return "list" if _LIST.match(text) else "paragraph"


def _markdown(rows: list[list[Any]]) -> str:
    """A table as Markdown, its first row the header."""
    cells = [[" ".join(str(cell or "").split()).replace("|", "\\|") for cell in row] for row in rows]
    lines = [f"| {' | '.join(row)} |" for row in cells]
    return "\n".join([lines[0], f"|{' --- |' * len(cells[0])}", *lines[1:]]) if lines else ""


def _continue(before: Block, table: Block) -> tuple[Block, int]:
    """A table that opens a page with the columns of the one closing the page before continues it: it takes that
    header, dropping its own first row when it repeats it."""
    header = before.text.split("\n")[:2]
    lines = table.text.split("\n")
    if lines[0].count(" | ") != header[0].count(" | "):
        return table, 0
    rows = lines[2:] if lines[0] == header[0] else [lines[0], *lines[2:]]
    return table.model_copy(update={"text": "\n".join([*header, *rows])}), 1


def _by_bookmarks(toc: list[tuple[int, str, int]], blocks: list[Block]) -> list[Start]:
    """A block belongs to the last bookmark before it; on a bookmark's page, it starts at the first block that
    begins with its title, else at the top of the page."""
    if not toc:
        return []
    cuts: list[int] = []
    for _, title, page in toc:
        # Bookmarks out of page order never take back blocks an earlier one already holds.
        later = [at for at in range(cuts[-1] if cuts else 0, len(blocks)) if (blocks[at].page or 0) >= page]
        on_page = [at for at in later if blocks[at].page == page]
        wanted = tokens(title)
        titled = [at for at in on_page if tokens(blocks[at].text)[: len(wanted)] == wanted]
        cuts.append(titled[0] if titled else on_page[0] if on_page else later[0] if later else len(blocks))
    starts = _leading(blocks[: cuts[0]], toc[0][0])
    for (level, title, page), cut, end in zip(toc, cuts, [*cuts[1:], len(blocks)], strict=True):
        starts.append(Start(id=f"s{len(starts) + 1}", title=title, level=level, page=page, blocks=blocks[cut:end]))
    return starts


def _by_headings(blocks: list[Block], sizes: dict[str, float]) -> list[Start]:
    """Each heading starts a section; bigger headings are higher levels."""
    levels = {size: level for level, size in enumerate(sorted(set(sizes.values()), reverse=True), start=1)}
    cuts = [at for at, block in enumerate(blocks) if block.id in sizes]
    if not cuts:
        return []
    starts = _leading(blocks[: cuts[0]], 1)
    for cut, end in zip(cuts, [*cuts[1:], len(blocks)], strict=True):
        heading = blocks[cut]
        starts.append(
            Start(
                id=f"s{len(starts) + 1}",
                title=heading.text,
                level=levels[sizes[heading.id]],
                page=heading.page,
                blocks=blocks[cut:end],
            )
        )
    return starts


def _by_page(blocks: list[Block], pages: int) -> list[Start]:
    return [
        Start(
            id=f"s{number}",
            title=f"Página {number}",
            level=1,
            page=number,
            blocks=[block for block in blocks if block.page == number],
        )
        for number in range(1, pages + 1)
    ]


def _leading(blocks: list[Block], level: int) -> list[Start]:
    """What comes before the first section, as a section of its own."""
    if not blocks:
        return []
    return [Start(id="s1", title=f"Página {blocks[0].page}", level=level, page=blocks[0].page, blocks=blocks)]


def _outline_only(titles: list[str], pages: int, note: str, limits: RetrievalLimits) -> DocIndex:
    return DocIndex(
        version=VERSION,
        source="pdf",
        outline="; ".join(titles)[: limits.description_chars],
        sections=[],
        blocks=[],
        passages=[],
        stats=DocStats(pages=pages, words=0, tables=0, figures=0),
        note=note,
    )
