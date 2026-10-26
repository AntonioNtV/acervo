from uuid import UUID

from acervo.core.errors import TwoFactorRequired, ValidationError
from acervo.domain.sort_keys import key_between
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.favorite import FavoritePlace
from acervo.schemas.node import NodeRead, NodeWithPath
from acervo.services.access_service import AccessService


class FavoriteService:
    """Each account's favorites across bases, in the order it set."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def listed(self, account_id: UUID) -> list[NodeWithPath]:
        # Hidden, not deleted: they come back when access does.
        visible = await self._uow.base_members.visible_kb_ids(account_id)
        access = AccessService(self._uow)
        for membership in await self._uow.memberships.of_account(account_id):
            try:
                await access.require_two_factor(account_id, membership.organization_id)
            except TwoFactorRequired:
                visible -= await self._uow.base_members.visible_kb_ids(account_id, membership.organization_id)
        nodes = [node for node in await self._uow.favorites.listed(account_id) if node.kb_id in visible]
        found = await self._uow.nodes.paths([node.id for node in nodes])
        return [NodeWithPath(**node.model_dump(), path=found[node.id]) for node in nodes]

    async def place(self, account_id: UUID, node_id: UUID, data: FavoritePlace) -> NodeRead:
        """Adds the node last, or puts it just before the favorite `before_id`; one already there moves."""
        node = await self._uow.nodes.live(node_id)
        if node.kind == "file":
            raise ValidationError("só páginas e pastas vão para os favoritos", {"id": str(node_id)})
        favorites = self._uow.favorites
        if data.before_id is None:
            sort = key_between(await favorites.last_sort(account_id, excluding=node.id), None)
        else:
            before = await self._uow.nodes.live(data.before_id)
            before_sort = await favorites.sort_of(account_id, before.id)
            if before.id == node.id or before_sort is None:
                raise ValidationError(
                    f"node {data.before_id} is not another favorite", {"before_id": str(data.before_id)}
                )
            sort = key_between(await favorites.last_sort(account_id, below=before_sort, excluding=node.id), before_sort)
        await favorites.put(account_id, node_id, sort)
        placed = await self._uow.nodes.live(node_id)
        await self._uow.commit()
        return placed

    async def remove(self, account_id: UUID, node_id: UUID) -> NodeRead:
        await self._uow.nodes.live(node_id)
        await self._uow.favorites.remove(account_id, node_id)
        removed = await self._uow.nodes.live(node_id)
        await self._uow.commit()
        return removed
