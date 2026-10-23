from uuid import UUID

from sqlalchemy import ColumnElement, func, select

from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.schemas.node import NodeCreate, NodeRead, NodeUpdate


def favorite_key() -> ColumnElement[str]:
    # Keys compare byte by byte, as `key_between` builds them, whatever the database's collation.
    return Node.favorite_sort.collate("C")


class FavoriteRepository(BaseRepository[Node, NodeRead, NodeCreate, NodeUpdate]):
    """The person's favorites across bases, kept as `node.favorite_sort`."""

    orm_model = Node
    read_schema = NodeRead

    async def listed(self) -> list[NodeRead]:
        """Live favorites of live bases in the person's order; trashed ones keep their key for the restore."""
        query = (
            select(Node)
            .join(Kb, Kb.id == Node.kb_id)
            .where(Node.favorite_sort.is_not(None), Node.deleted_at.is_(None), Kb.deleted_at.is_(None))
            .order_by(favorite_key(), Node.id)
            .execution_options(populate_existing=True)
        )
        return [self._to_read(node) for node in await self._session.scalars(query)]

    async def last_sort(self, *, below: str | None = None, excluding: UUID | None = None) -> str | None:
        """The highest favorite key, or the highest one under `below`, trashed favorites included."""
        query = select(func.max(favorite_key())).where(Node.favorite_sort.is_not(None))
        if below is not None:
            query = query.where(favorite_key() < below)
        if excluding is not None:
            query = query.where(Node.id != excluding)
        return await self._session.scalar(query)

    async def sort_of(self, node_id: UUID) -> str | None:
        """The node's favorite key; None when it is not a favorite."""
        return await self._session.scalar(select(Node.favorite_sort).where(Node.id == node_id))
