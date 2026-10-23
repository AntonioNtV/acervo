from uuid import UUID

from sqlalchemy import CTE, ColumnElement, SQLColumnExpression, exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by

from acervo.core.errors import NotFoundError, ValidationError
from acervo.db.models.file import File
from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.schemas.node import NodeCreate, NodeKind, NodeRead, NodeUpdate, TreeNode

SEARCH_LIMIT = 50


def sort_key() -> ColumnElement[str]:
    # Keys compare byte by byte, as `key_between` builds them, whatever the database's collation.
    return Node.sort.collate("C")


def siblings(kb_id: UUID, parent_id: UUID | None) -> list[ColumnElement[bool]]:
    parent = Node.parent_id.is_(None) if parent_id is None else Node.parent_id == parent_id
    return [Node.kb_id == kb_id, parent, Node.deleted_at.is_(None)]


def folded(text: SQLColumnExpression[str]) -> ColumnElement[str]:
    """Lowercase and without accents, the same expression the trigram index holds."""
    return func.acervo.immutable_unaccent(func.lower(text))


def contains(column: SQLColumnExpression[str], query: str) -> ColumnElement[bool]:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return folded(column).like(func.concat("%", folded(literal(escaped)), "%"), escape="\\")


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

    async def live_parent(self, kb_id: UUID, parent_id: UUID | None) -> None:
        """The live base, and the live folder or page of it when `parent_id` is given (None is the base's root)."""
        # populate_existing: trash and restore update rows in bulk, behind the identity map.
        kb = await self._session.get(Kb, kb_id, populate_existing=True)
        if kb is None or kb.deleted_at is not None:
            raise NotFoundError(f"kb {kb_id} not found", {"id": str(kb_id)})
        if parent_id is None:
            return
        parent = await self._session.get(Node, parent_id, populate_existing=True)
        if parent is None or parent.deleted_at is not None:
            raise NotFoundError(f"node {parent_id} not found", {"id": str(parent_id)})
        if parent.kb_id != kb_id:
            raise ValidationError("o destino não está nesta base", {"parent_id": str(parent_id)})
        if parent.kind == "file":
            raise ValidationError("um arquivo não guarda itens", {"parent_id": str(parent_id)})

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

    async def live(self, node_id: UUID) -> NodeRead:
        # populate_existing: trash and restore update rows in bulk, behind the identity map.
        node = await self._session.get(Node, node_id, populate_existing=True)
        if node is None or node.deleted_at is not None:
            raise NotFoundError(f"node {node_id} not found", {"id": str(node_id)})
        return self._to_read(node)

    async def trashed_root(self, node_id: UUID) -> NodeRead:
        """A node trashed on its own, not one that went with a folder."""
        node = await self._session.get(Node, node_id, populate_existing=True)
        if node is None or node.trashed_with != node.id:
            raise NotFoundError(f"node {node_id} is not in the trash", {"id": str(node_id)})
        return self._to_read(node)

    async def is_trashed(self, node_id: UUID) -> bool:
        return bool(await self._session.scalar(select(Node.deleted_at.is_not(None)).where(Node.id == node_id)))

    async def children(self, kb_id: UUID, parent_id: UUID | None) -> list[TreeNode]:
        """Live children in the person's order, each with how many live children it has and its file's facts."""
        child = Node.__table__.alias("child")
        child_count = (
            select(func.count()).where(child.c.parent_id == Node.id, child.c.deleted_at.is_(None)).scalar_subquery()
        )
        query = (
            select(Node, func.coalesce(File.protected, False), child_count, File.pages, File.size)
            .outerjoin(File, File.node_id == Node.id)
            .where(*siblings(kb_id, parent_id))
            .order_by(sort_key(), Node.id)
            .execution_options(populate_existing=True)
        )
        rows = await self._session.execute(query)
        return [
            TreeNode(
                **self._to_read(node).model_dump(),
                protected=protected,
                child_count=count,
                pages=pages,
                size=size,
            )
            for node, protected, count, pages, size in rows
        ]

    async def live_in(self, kb_id: UUID) -> list[NodeRead]:
        """Every live node of the base, siblings in the person's order."""
        query = select(Node).where(Node.kb_id == kb_id, Node.deleted_at.is_(None)).order_by(sort_key(), Node.id)
        nodes = await self._session.scalars(query.execution_options(populate_existing=True))
        return [self._to_read(node) for node in nodes]

    async def ancestors(self, node_id: UUID) -> set[UUID]:
        """The node itself and every node above it."""
        return set(await self._session.scalars(select(upwards([node_id]).c.id)))

    async def last_sort(
        self, kb_id: UUID, parent_id: UUID | None, *, below: str | None = None, excluding: UUID | None = None
    ) -> str | None:
        """The highest sort key among the live siblings, or the highest one under `below`."""
        query = select(func.max(sort_key())).where(*siblings(kb_id, parent_id))
        if below is not None:
            query = query.where(sort_key() < below)
        if excluding is not None:
            query = query.where(Node.id != excluding)
        return await self._session.scalar(query)

    async def next_sort(self, kb_id: UUID, parent_id: UUID | None, above: str) -> str | None:
        """The lowest sort key among the live siblings over `above`."""
        query = select(func.min(sort_key())).where(*siblings(kb_id, parent_id), sort_key() > above)
        return await self._session.scalar(query)

    async def sort_taken(self, kb_id: UUID, parent_id: UUID | None, sort: str) -> bool:
        return bool(await self._session.scalar(select(exists().where(*siblings(kb_id, parent_id), sort_key() == sort))))

    async def trash_subtree(self, node_id: UUID) -> None:
        """Hides the node and its whole live subtree; what was already in the trash keeps its own `trashed_with`."""
        subtree = select(Node.id).where(Node.id == node_id).cte("subtree", recursive=True)
        subtree = subtree.union_all(
            select(Node.id).join(subtree, Node.parent_id == subtree.c.id).where(Node.deleted_at.is_(None))
        )
        await self._session.execute(
            update(Node)
            .where(Node.id.in_(select(subtree.c.id)))
            .values(deleted_at=func.now(), trashed_with=node_id)
            .execution_options(synchronize_session=False)
        )

    async def subtree(self, node_id: UUID) -> list[NodeRead]:
        """The node and every node under it, trashed ones included."""
        down = select(Node.id).where(Node.id == node_id).cte("down", recursive=True)
        down = down.union_all(select(Node.id).join(down, Node.parent_id == down.c.id))
        query = select(Node).where(Node.id.in_(select(down.c.id))).execution_options(populate_existing=True)
        return [self._to_read(node) for node in await self._session.scalars(query)]

    async def set_base(self, node_ids: list[UUID], kb_id: UUID) -> None:
        await self._session.execute(update(Node).where(Node.id.in_(node_ids)).values(kb_id=kb_id))

    async def restore_trashed_with(self, node_id: UUID) -> None:
        """Brings back every node the trashing of `node_id` hid."""
        await self._session.execute(
            update(Node)
            .where(Node.trashed_with == node_id)
            .values(deleted_at=None, trashed_with=None)
            .execution_options(synchronize_session=False)
        )

    async def trash_roots(self, kb_id: UUID) -> list[NodeRead]:
        """One node per trashing, most recent first."""
        query = select(Node).where(Node.kb_id == kb_id, Node.trashed_with == Node.id).order_by(Node.deleted_at.desc())
        nodes = await self._session.scalars(query.execution_options(populate_existing=True))
        return [self._to_read(node) for node in nodes]

    async def search(self, kb_id: UUID, query: str) -> list[NodeRead]:
        """The person's name search (rule 2 of CLAUDE.md): titles only, never an agent's way to find content."""
        closeness = func.similarity(folded(Node.title), folded(literal(query)))
        rows = (
            select(Node)
            .where(Node.kb_id == kb_id, Node.deleted_at.is_(None), contains(Node.title, query))
            .order_by(closeness.desc(), Node.title)
            .limit(SEARCH_LIMIT)
        )
        return [self._to_read(node) for node in await self._session.scalars(rows)]
