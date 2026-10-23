"""The statistics branch of a document: counts, so "how many" is answered from them, never from samples."""

import re
import unicodedata

from acervo.domain.index import Block, DocIndex, DocStats

_TOKEN = re.compile(r"\w+")


def tokens(text: str) -> list[str]:
    """Lower case, accents dropped: `Prêmio` and `premio` are the same token."""
    return _TOKEN.findall(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower())


def doc_stats(pages: int, blocks: list[Block], continued_tables: int = 0) -> DocStats:
    """`continued_tables` are table blocks that continue one on the page before, so a table is counted once."""
    return DocStats(
        pages=pages,
        words=sum(len(tokens(block.text)) for block in blocks),
        tables=sum(block.kind == "table" for block in blocks) - continued_tables,
        figures=sum(block.kind == "figure" for block in blocks),
    )


def term_count(index: DocIndex, term: str) -> int:
    """How often `term` (one or more whole tokens) appears in the document."""
    wanted = tokens(term)
    if not wanted:
        return 0
    count = 0
    for block in index.blocks:
        found = tokens(block.text)
        count += sum(found[at : at + len(wanted)] == wanted for at in range(len(found) - len(wanted) + 1))
    return count
