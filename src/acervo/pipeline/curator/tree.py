"""What the caller hands the pipeline: a snapshot of a base's tree and a way to read one page."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr

from acervo.domain.cards import NodeKind


class SnapshotNode(BaseModel):
    """One live node of the base, as the decisions see it."""

    id: UUID
    parent_id: UUID | None = Field(description="Null for a node at the base's root.")
    kind: NodeKind
    title: str = Field(description="A file's keeps its extension.")
    description: str = Field(default="", description="The person's own; one an agent wrote is not kept.")
    built: str = Field(default="", description="From the index: a document's outline, a folder's children's.")
    active_at: datetime = Field(description="Its most recent activity: ranks children past Jev's 255 options.")


class TreeSnapshot(BaseModel):
    """Every live node of a base, siblings in their sort order."""

    nodes: list[SnapshotNode]
    # Positions in `nodes`, not the nodes: a caller may swap a node for an updated copy in place.
    _at: dict[UUID, int] = PrivateAttr(default_factory=dict)
    _under: dict[UUID | None, list[int]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context: Any) -> None:
        for index, node in enumerate(self.nodes):
            self._at[node.id] = index
            self._under.setdefault(node.parent_id, []).append(index)

    def node(self, id: UUID) -> SnapshotNode:
        return self.nodes[self._at[id]]

    def children(self, parent: SnapshotNode | None) -> list[SnapshotNode]:
        return [self.nodes[index] for index in self._under.get(parent.id if parent else None, [])]

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
