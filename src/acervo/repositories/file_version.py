from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from acervo.db.models.file_version import FileVersion
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.repositories.file import of_base
from acervo.schemas.file import FileVersionCreate, FileVersionRead
from acervo.schemas.node import NodeRead


class FileVersionRepository(BaseRepository[FileVersion, FileVersionRead, FileVersionCreate, BaseModel]):
    orm_model = FileVersion
    read_schema = FileVersionRead

    async def history(self, node_id: UUID) -> list[FileVersionRead]:
        """The file's older contents, newest first; the current one is not in it."""
        query = (
            select(FileVersion)
            .where(FileVersion.node_id == node_id)
            .order_by(FileVersion.replaced_at.desc(), FileVersion.id.desc())
        )
        return [self._to_read(version) for version in await self._session.scalars(query)]

    async def holder(self, kb_id: UUID, sha256: str, other_than: UUID | None = None) -> NodeRead | None:
        """A node of the base that had this content in its history."""
        query = (
            select(Node)
            .join(FileVersion, FileVersion.node_id == Node.id)
            .where(*of_base(kb_id, other_than), FileVersion.sha256 == sha256)
            .limit(1)
        )
        node = await self._session.scalar(query)
        return None if node is None else NodeRead.model_validate(node)
