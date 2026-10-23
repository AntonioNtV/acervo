from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from acervo.db.models.node_index import NodeIndex
from acervo.domain.index import DocIndex
from acervo.schemas.index import IndexState, NodeIndexParsed


class NodeIndexRepository:
    """One index per file or page. A build is keyed by the version it is of; the previous index stays readable
    until the build that is still current finishes. Never commits: the UnitOfWork does."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, node_id: UUID) -> NodeIndexParsed | None:
        row = await self._session.get(NodeIndex, node_id, options=[undefer(NodeIndex.parsed)], populate_existing=True)
        return None if row is None else NodeIndexParsed.model_validate(row)

    async def outlines(self, node_ids: list[UUID]) -> dict[UUID, str]:
        """The readable outline of each node that has one; never loads the parsed index."""
        query = select(NodeIndex.node_id, NodeIndex.outline).where(NodeIndex.node_id.in_(node_ids))
        return {node_id: outline for node_id, outline in await self._session.execute(query) if outline}

    async def states(self, node_ids: list[UUID]) -> dict[UUID, IndexState]:
        query = select(NodeIndex.node_id, NodeIndex.status).where(NodeIndex.node_id.in_(node_ids))
        found = {node_id: status for node_id, status in await self._session.execute(query)}
        return {node_id: cast(IndexState, found.get(node_id, "none")) for node_id in node_ids}

    async def start(self, node_id: UUID, key: str) -> None:
        """Marks the version `key` as building; a later `start` supersedes it."""
        row = await self._session.get(NodeIndex, node_id, populate_existing=True)
        if row is None:
            self._session.add(NodeIndex(node_id=node_id, version_key=key, building_key=key, status="building"))
        else:
            row.building_key, row.status, row.error = key, "building", None
        await self._session.flush()

    async def finish(self, node_id: UUID, key: str, index: DocIndex) -> bool:
        """Swaps in the index of `key`; False, changing nothing, when another build superseded it."""
        row = await self._building(node_id, key)
        if row is None:
            return False
        row.version_key, row.building_key, row.status, row.error = key, None, "ready", None
        row.outline, row.parsed = index.outline, index.model_dump(mode="json")
        await self._session.flush()
        return True

    async def fail(self, node_id: UUID, key: str, error: str) -> bool:
        """Marks the build of `key` failed, keeping the previous index readable; False when superseded."""
        row = await self._building(node_id, key)
        if row is None:
            return False
        row.building_key, row.status, row.error = None, "failed", error
        await self._session.flush()
        return True

    async def _building(self, node_id: UUID, key: str) -> NodeIndex | None:
        row = await self._session.get(NodeIndex, node_id, populate_existing=True)
        return row if row is not None and row.building_key == key else None
