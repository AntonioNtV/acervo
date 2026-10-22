from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete, func, select

from acervo.db.models.node import Node
from acervo.db.models.page_link import PageLink
from acervo.repositories.base import BaseRepository
from acervo.schemas.node import NodeRead
from acervo.schemas.page import PageLinkCreate, PageLinkRead


class PageLinkRepository(BaseRepository[PageLink, PageLinkRead, PageLinkCreate, BaseModel]):
    orm_model = PageLink
    read_schema = PageLinkRead

    async def replace(self, kb_id: UUID, node_id: UUID, targets: set[str]) -> None:
        """The page's rows, rewritten from the targets of its newest version."""
        await self._session.execute(delete(PageLink).where(PageLink.from_node_id == node_id))
        await self.create_many([PageLinkCreate(kb_id=kb_id, from_node_id=node_id, target=t) for t in targets])

    async def targets(self, node_id: UUID) -> list[str]:
        return list(await self._session.scalars(select(PageLink.target).where(PageLink.from_node_id == node_id)))

    async def candidates(self, kb_id: UUID, targets: list[str]) -> list[NodeRead]:
        """Live pages of the base whose title is one of the targets."""
        query = select(Node).where(
            Node.kb_id == kb_id,
            Node.kind == "page",
            Node.deleted_at.is_(None),
            func.lower(Node.title).in_(targets),
        )
        # populate_existing: trash and restore update rows in bulk, behind the identity map.
        query = query.execution_options(populate_existing=True)
        return [NodeRead.model_validate(node) for node in await self._session.scalars(query)]

    async def linking(self, kb_id: UUID, target: str) -> list[NodeRead]:
        """Live pages of the base with a link to `target`."""
        query = (
            select(Node)
            .join(PageLink, PageLink.from_node_id == Node.id)
            .where(PageLink.kb_id == kb_id, PageLink.target == target, Node.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )
        return [NodeRead.model_validate(node) for node in await self._session.scalars(query)]
