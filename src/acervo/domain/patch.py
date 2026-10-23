"""Lines an agent adds to a section of a page, addressed by anchor and line text, never by line number."""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from acervo.domain.sections import sections

Op = Literal["append", "insert_after", "replace", "new_section"]


class Stale(Exception):
    """The section or the line a patch refers to is not in the text any more."""


@dataclass(frozen=True)
class Patch:
    anchor: str
    op: Op
    lines: list[str]
    # For insert_after and replace: the exact text it refers to; several lines for a replace.
    line: str | None = None


def provenance(source: str, day: date, proposal_id: UUID) -> str:
    """`<!-- origem: chat · 2026-10-22 · proposta 8f3a -->`."""
    return f"<!-- origem: {source} · {day.isoformat()} · proposta {proposal_id.hex[:4]} -->"


def apply(markdown: str, patch: Patch, origin: str) -> str:
    """`markdown` with the patch's lines in, each followed by `origin`. The section is found by its anchor in the
    text given, so applying to the newest text is the rebase: a section that moved is still found, one that is gone
    raises `Stale`."""
    lines = markdown.splitlines()
    start, end = _span(lines, patch.anchor)
    added = [_marked(line, origin) for line in patch.lines]
    if patch.op == "append":
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        at, cut = end, end
    elif patch.op == "new_section":
        at, cut = end, end
        added = ([""] if at and lines[at - 1].strip() else []) + added + ([""] if at < len(lines) else [])
    else:
        wanted = (patch.line or "").splitlines()
        # Below the heading: a replace or an insert never touches it, so the section keeps its anchor.
        body = start + 1 if patch.anchor else start
        found = _find(lines[body:end], wanted)
        if found is None:
            raise Stale(f"line not in section {patch.anchor!r}")
        first, after = body + found, body + found + len(wanted)
        at, cut = (after, after) if patch.op == "insert_after" else (first, after)
    text = "\n".join(lines[:at] + added + lines[cut:])
    return text + "\n" if text else text


def _marked(line: str, origin: str) -> str:
    # A comment after a heading would become part of its text, and so of its anchor.
    if not line.strip() or line.lstrip().startswith("#"):
        return line
    return f"{line} {origin}"


def _span(lines: list[str], anchor: str) -> tuple[int, int]:
    """The section's first line and the line after its last; "" is the text before the first `##`."""
    starts: list[int] = []
    in_code = False
    for index, line in enumerate(lines):
        if line.startswith(("```", "~~~")):
            in_code = not in_code
        elif not in_code and sections(line):
            starts.append(index)
    anchors = ["", *(section.anchor for section in sections("\n".join(lines)))]
    bounds = [0, *starts, len(lines)]
    if anchor not in anchors:
        raise Stale(f"section {anchor!r} not in the page")
    index = anchors.index(anchor)
    return bounds[index], bounds[index + 1]


def _find(lines: list[str], wanted: list[str]) -> int | None:
    if not wanted:
        return None
    for index in range(len(lines) - len(wanted) + 1):
        if lines[index : index + len(wanted)] == wanted:
            return index
    return None
