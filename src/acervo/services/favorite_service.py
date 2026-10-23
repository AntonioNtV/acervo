from uuid import UUID

from acervo.core.errors import ValidationError
from acervo.domain.sort_keys import key_between
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.favorite import FavoritePlace
from acervo.schemas.node import NodeRead, NodeUpdate, NodeWithPath


class FavoriteService:
    """The person's favorites across bases, in the order they set."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def listed(self) -> list[NodeWithPath]:
        nodes = await self._uow.favorites.listed()
        found = await self._uow.nodes.paths([node.id for node in nodes])
        return [NodeWithPath(**node.model_dump(), path=found[node.id]) for node in nodes]

    async def place(self, node_id: UUID, data: FavoritePlace) -> NodeRead:
        """Adds the node last, or puts it just before the favorite `before_id`; one already there moves."""
        node = await self._uow.nodes.live(node_id)
        if node.kind == "file":
            raise ValidationError("só páginas e pastas vão para os favoritos", {"id": str(node_id)})
        favorites = self._uow.favorites
        if data.before_id is None:
            sort = key_between(await favorites.last_sort(excluding=node.id), None)
        else:
            before = await self._uow.nodes.live(data.before_id)
            before_sort = await favorites.sort_of(before.id)
            if before.id == node.id or before_sort is None:
                raise ValidationError(
                    f"node {data.before_id} is not another favorite", {"before_id": str(data.before_id)}
                )
            sort = key_between(await favorites.last_sort(below=before_sort, excluding=node.id), before_sort)
        placed = await self._uow.nodes.update(node_id, NodeUpdate(favorite_sort=sort))
        await self._uow.commit()
        return placed

    async def remove(self, node_id: UUID) -> NodeRead:
        await self._uow.nodes.live(node_id)
        removed = await self._uow.nodes.update(node_id, NodeUpdate(favorite_sort=None))
        await self._uow.commit()
        return removed
