"""What the caller hands the pipeline: a snapshot of a base's tree and a way to read one page."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.domain.cards import NodeKind


class SnapshotNode(BaseModel):
    """One live node of the base, as the decisions see it."""

    id: UUID
    parent_id: UUID | None = Field(description="Null for a node at the base's root.")
    kind: NodeKind
    title: str = Field(description="A file's keeps its extension.")
    description: str = ""
    active_at: datetime = Field(description="Its most recent activity: ranks children past Jev's 255 options.")


class TreeSnapshot(BaseModel):
    """Every live node of a base, siblings in their sort order."""

    nodes: list[SnapshotNode]

    def node(self, id: UUID) -> SnapshotNode:
        return next(node for node in self.nodes if node.id == id)

    def children(self, parent: SnapshotNode | None) -> list[SnapshotNode]:
        parent_id = parent.id if parent else None
        return [node for node in self.nodes if node.parent_id == parent_id]

    def path(self, node: SnapshotNode | None) -> str:
        """Titles from the root down to the node, joined by /; empty for the root."""
        titles: list[str] = []
        while node is not None:
            titles.append(node.title)
            node = self.node(node.parent_id) if node.parent_id else None
        return "/".join(reversed(titles))


class PageText(BaseModel):
    """The newest version of a page, which the lines are written against."""

    page_id: UUID
    version_id: UUID
    markdown: str


ReadPage = Callable[[UUID], Awaitable[PageText]]
