from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import with_expression
from sqlalchemy.orm.interfaces import ORMOption

from acervo.db.models.favorite import Favorite
from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.repositories.node import favorited
from acervo.schemas.node import NodeCreate, NodeRead, NodeUpdate


def favorite_key() -> ColumnElement[str]:
    # Keys compare byte by byte, as `key_between` builds them, whatever the database's collation.
    return Favorite.sort.collate("C")


class FavoriteRepository(BaseRepository[Node, NodeRead, NodeCreate, NodeUpdate]):
    """Each account's favorites across bases, kept in the `favorite` table."""

    orm_model = Node
    read_schema = NodeRead

    def _options(self) -> list[ORMOption]:
        return [with_expression(Node.favorite, favorited(self._session.info.get("account_id")))]

    async def listed(self, account_id: UUID) -> list[NodeRead]:
        """Live favorites of live bases in the account's order; trashed ones keep their key for the restore."""
        query = (
            self._select()
            .join(Favorite, Favorite.node_id == Node.id)
            .join(Kb, Kb.id == Node.kb_id)
            .where(Favorite.account_id == account_id, Node.deleted_at.is_(None), Kb.deleted_at.is_(None))
            .order_by(favorite_key(), Node.id)
        )
        return [self._to_read(node) for node in await self._session.scalars(query)]

    async def last_sort(
        self, account_id: UUID, *, below: str | None = None, excluding: UUID | None = None
    ) -> str | None:
        """The account's highest favorite key, or the highest one under `below`, trashed favorites included."""
        query = select(func.max(favorite_key())).where(Favorite.account_id == account_id)
        if below is not None:
            query = query.where(favorite_key() < below)
        if excluding is not None:
            query = query.where(Favorite.node_id != excluding)
        return await self._session.scalar(query)

    async def sort_of(self, account_id: UUID, node_id: UUID) -> str | None:
        """The node's key among the account's favorites; None when it is not one."""
        query = select(Favorite.sort).where(Favorite.account_id == account_id, Favorite.node_id == node_id)
        return await self._session.scalar(query)

    async def put(self, account_id: UUID, node_id: UUID, sort: str) -> None:
        """Adds the node to the account's favorites at `sort`, or moves it there."""
        upsert = insert(Favorite).values(account_id=account_id, node_id=node_id, sort=sort)
        await self._session.execute(
            upsert.on_conflict_do_update(
                index_elements=[Favorite.account_id, Favorite.node_id], set_={"sort": sort, "updated_at": func.now()}
            )
        )

    async def remove(self, account_id: UUID, node_id: UUID) -> None:
        query = delete(Favorite).where(Favorite.account_id == account_id, Favorite.node_id == node_id)
        await self._session.execute(query)
