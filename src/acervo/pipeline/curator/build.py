"""The payload of the proposal the policy chose; the lines come from the LLM `patch` role (skill `curator-agent`)."""

from typing import Literal

from acervo.domain.cards import Card, PatchRequest
from acervo.model_clients.writer import Writer
from acervo.pipeline.curator.page_check import PageCheck
from acervo.pipeline.curator.tree import PageText, SnapshotNode, TreeSnapshot
from acervo.schemas.proposal import (
    ConflictPayload,
    CreatePagePayload,
    PatchPayload,
    ReplacePdfPayload,
    SavePdfPayload,
)


async def patch(writer: Writer, card: Card, page: PageText, path: str, check: PageCheck) -> PatchPayload:
    """An edit of the line about the same thing, or lines appended to the chosen section."""
    action: Literal["append", "edit"] = "edit" if check.line else "append"
    request = PatchRequest(
        section_markdown=check.section.markdown, heading=check.section.heading, action=action, card=card
    )
    written = await writer.patch(request)
    return PatchPayload(
        kind=action,
        page_id=page.page_id,
        path=path,
        base_version_id=page.version_id,
        anchor=check.section.anchor,
        heading=check.section.heading,
        op="replace" if check.line else "append",
        line=check.line,
        lines=written.lines,
    )


async def conflict(writer: Writer, card: Card, page: PageText, path: str, check: PageCheck) -> ConflictPayload:
    """What the page says now next to what the input says, written as the edit it would be."""
    request = PatchRequest(
        section_markdown=check.section.markdown, heading=check.section.heading, action="edit", card=card
    )
    written = await writer.patch(request)
    return ConflictPayload(
        page_id=page.page_id,
        path=path,
        base_version_id=page.version_id,
        anchor=check.section.anchor,
        heading=check.section.heading,
        current=check.line or check.section.markdown,
        new="\n".join(written.lines),
    )


async def create_page(writer: Writer, card: Card, tree: TreeSnapshot, parent: SnapshotNode | None) -> CreatePagePayload:
    written = await writer.patch(PatchRequest(section_markdown="", heading=card.title, action="append", card=card))
    return CreatePagePayload(
        parent_id=parent.id if parent else None,
        parent_path=tree.path(parent),
        title=card.title,
        markdown="\n".join([f"# {card.title}", "", *written.lines, ""]),
    )


def save_pdf(tree: TreeSnapshot, parent: SnapshotNode | None, name: str) -> SavePdfPayload:
    return SavePdfPayload(
        parent_id=parent.id if parent else None,
        parent_path=tree.path(parent),
        name=name if name.lower().endswith(".pdf") else f"{name}.pdf",
    )


def replace_pdf(tree: TreeSnapshot, node: SnapshotNode) -> ReplacePdfPayload:
    return ReplacePdfPayload(node_id=node.id, path=tree.path(node))
