from uuid import UUID

from sqlalchemy import CTE, ColumnElement, exists, func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from acervo.core.errors import NotFoundError, ValidationError
from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.schemas.node import NodeCreate, NodeKind, NodeRead, NodeUpdate


def sort_key() -> ColumnElement[str]:
    # Keys compare byte by byte, as `key_between` builds them, whatever the database's collation.
    return Node.sort.collate("C")


def siblings(kb_id: UUID, parent_id: UUID | None) -> list[ColumnElement[bool]]:
    parent = Node.parent_id.is_(None) if parent_id is None else Node.parent_id == parent_id
    return [Node.kb_id == kb_id, parent, Node.deleted_at.is_(None)]


def upwards(node_ids: list[UUID]) -> CTE:
    """Each start node and its ancestors, with their distance from the start."""
    up = (
        select(Node.id.label("start_id"), Node.id, Node.parent_id, Node.title, literal(0).label("depth"))
        .where(Node.id.in_(node_ids))
        .cte("up", recursive=True)
    )
    return up.union_all(
        select(up.c.start_id, Node.id, Node.parent_id, Node.title, up.c.depth + 1).join(Node, Node.id == up.c.parent_id)
    )


class NodeRepository(BaseRepository[Node, NodeRead, NodeCreate, NodeUpdate]):
    orm_model = Node
    read_schema = NodeRead

    async def paths(self, node_ids: list[UUID]) -> dict[UUID, str]:
        """Each node's path: the titles from the root down to it, joined by "/"."""
        if not node_ids:
            return {}
        up = upwards(node_ids)
        joined = func.string_agg(up.c.title, aggregate_order_by(literal("/"), up.c.depth.desc()))
        rows = await self._session.execute(select(up.c.start_id, joined).group_by(up.c.start_id))
        return {start_id: joined_path for start_id, joined_path in rows}

    async def path(self, node_id: UUID) -> str:
        found = await self.paths([node_id])
        if node_id not in found:
            raise NotFoundError(f"node {node_id} not found", {"id": str(node_id)})
        return found[node_id]

    async def live_folder(self, kb_id: UUID, folder_id: UUID | None) -> None:
        """The live base, and the live folder of it when `folder_id` is given (None is the base's root)."""
        # populate_existing: trash and restore update rows in bulk, behind the identity map.
        kb = await self._session.get(Kb, kb_id, populate_existing=True)
        if kb is None or kb.deleted_at is not None:
            raise NotFoundError(f"kb {kb_id} not found", {"id": str(kb_id)})
        if folder_id is None:
            return
        folder = await self._session.get(Node, folder_id, populate_existing=True)
        if folder is None or folder.deleted_at is not None:
            raise NotFoundError(f"node {folder_id} not found", {"id": str(folder_id)})
        if folder.kb_id != kb_id or folder.kind != "folder":
            raise ValidationError("a pasta não está nesta base", {"folder_id": str(folder_id)})

    async def title_taken(self, kb_id: UUID, parent_id: UUID | None, kind: NodeKind, title: str) -> bool:
        """The check behind the live-sibling unique index, to refuse with "já existe" before the insert fails."""
        query = select(
            exists().where(
                *siblings(kb_id, parent_id),
                Node.kind == kind,
                func.lower(Node.title) == func.lower(title),
            )
        )
        return bool(await self._session.scalar(query))

    async def last_sort(self, kb_id: UUID, parent_id: UUID | None) -> str | None:
        return await self._session.scalar(select(func.max(sort_key())).where(*siblings(kb_id, parent_id)))
