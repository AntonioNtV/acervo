from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select

from acervo.core.errors import NotFoundError
from acervo.db.models.account import Account
from acervo.db.models.page_version import PageVersion
from acervo.repositories.base import BaseRepository
from acervo.schemas.page import PageVersionCreate, PageVersionRead, PageVersionSummary


class PageVersionRepository(BaseRepository[PageVersion, PageVersionRead, PageVersionCreate, BaseModel]):
    orm_model = PageVersion
    read_schema = PageVersionRead

    async def add(self, data: PageVersionCreate) -> PageVersionRead:
        # The database clock, not the transaction's: several versions written in one transaction keep their order.
        return await self.create(data, created_at=await self._session.scalar(select(func.clock_timestamp())))

    async def current(self, node_id: UUID) -> PageVersionRead:
        version = await self._session.scalar(
            select(PageVersion).where(PageVersion.node_id == node_id).order_by(PageVersion.created_at.desc()).limit(1)
        )
        if version is None:
            raise NotFoundError(f"page {node_id} has no version", {"id": str(node_id)})
        return self._to_read(version)

    async def history(self, node_id: UUID) -> list[PageVersionSummary]:
        """Every version of the page, newest first, without its text."""
        rows = await self._session.execute(
            select(
                PageVersion.id,
                PageVersion.created_at,
                PageVersion.edit_started_at,
                PageVersion.edit_ended_at,
                PageVersion.author_id,
                Account.name.label("author"),
                PageVersion.author_known,
            )
            .outerjoin(Account, Account.id == PageVersion.author_id)
            .where(PageVersion.node_id == node_id)
            .order_by(PageVersion.created_at.desc())
        )
        return [PageVersionSummary.model_validate(row) for row in rows]

    async def previous_markdown(self, version: PageVersionRead) -> str:
        """The text of the version just before `version`; empty for the first one."""
        query = (
            select(PageVersion.markdown)
            .where(PageVersion.node_id == version.node_id, PageVersion.created_at < version.created_at)
            .order_by(PageVersion.created_at.desc())
            .limit(1)
        )
        return await self._session.scalar(query) or ""
