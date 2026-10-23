"""A Markdown page's index: its `##` sections under the anchors the page view uses (skill `markdown-pages`)."""

import re

from acervo.core.settings import RetrievalLimits
from acervo.domain.index import Block, BlockKind, DocIndex
from acervo.domain.patch import span
from acervo.domain.sections import sections
from acervo.pipeline.index.passages import Start, assemble
from acervo.pipeline.index.stats import doc_stats

_HEADING = re.compile(r"^#{1,6}\s")
_LIST = re.compile(r"^\s*([-*+]|\d+[.)])\s")
# The text before the first `##` has anchor "" and no heading of its own.
_INTRO = "Início"


def index_markdown(text: str, limits: RetrievalLimits) -> DocIndex:
    lines = text.splitlines()
    blocks: list[Block] = []
    starts: list[Start] = []
    for anchor, heading in [("", None), *((found.anchor, found.heading) for found in sections(text))]:
        first, last = span(lines, anchor)
        own = _blocks(lines[first:last], first=len(blocks))
        if heading is None and not own:
            continue
        title = heading or next((block.text.lstrip("# ") for block in own if block.text.startswith("# ")), _INTRO)
        starts.append(Start(id=anchor, title=title, level=2, page=None, blocks=own))
        blocks += own
    return assemble("markdown", starts, blocks, None, limits, doc_stats(0, blocks))


def _blocks(lines: list[str], first: int) -> list[Block]:
    """Paragraphs, lists, tables and headings split at blank lines; a code fence stays whole and makes no heading."""
    chunks: list[list[str]] = [[]]
    in_code = False
    for line in lines:
        if line.startswith(("```", "~~~")):
            in_code = not in_code
        elif not in_code and (not line.strip() or _HEADING.match(line)):
            chunks += [[line], []] if line.strip() else [[]]
            continue
        chunks[-1].append(line)
    return [
        Block(id=f"b{first + number}", kind=_kind(chunk), text="\n".join(chunk))
        for number, chunk in enumerate((chunk for chunk in chunks if chunk), start=1)
    ]


def _kind(chunk: list[str]) -> BlockKind:
    if _HEADING.match(chunk[0]):
        return "heading"
    if chunk[0].lstrip().startswith("|"):
        return "table"
    return "list" if _LIST.match(chunk[0]) else "paragraph"
