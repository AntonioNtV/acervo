from uuid import UUID

from sqlalchemy import ColumnElement, select

from acervo.core.errors import NotFoundError
from acervo.db.models.file import File
from acervo.db.models.node import Node
from acervo.repositories.base import BaseRepository
from acervo.schemas.file import FileContent, FileCreate, FileRead
from acervo.schemas.node import NodeRead


def of_base(kb_id: UUID, other_than: UUID | None) -> list[ColumnElement[bool]]:
    """Every node of the base, trashed ones included, but `other_than`."""
    return [Node.kb_id == kb_id, *([Node.id != other_than] if other_than else [])]


class FileRepository(BaseRepository[File, FileRead, FileCreate, FileContent]):
    orm_model = File
    read_schema = FileRead

    async def of_node(self, node_id: UUID) -> FileRead:
        file = await self.get_by(node_id=node_id)
        if file is None:
            raise NotFoundError(f"file of node {node_id} not found", {"id": str(node_id)})
        return file

    async def set_content(self, id: UUID, content: FileContent) -> FileRead:
        return await self.update(id, content.only_content())

    async def holder(self, kb_id: UUID, sha256: str, other_than: UUID | None = None) -> NodeRead | None:
        """A node of the base whose current content has this hash."""
        query = (
            select(Node)
            .join(File, File.node_id == Node.id)
            .where(*of_base(kb_id, other_than), File.sha256 == sha256)
            .limit(1)
        )
        node = await self._session.scalar(query)
        return None if node is None else NodeRead.model_validate(node)

    async def held_in(self, kb_id: UUID, node_ids: list[UUID]) -> list[str]:
        """Titles of the live files among `node_ids` whose current content a live file of the base already has."""
        live = (
            select(File.sha256)
            .join(Node, Node.id == File.node_id)
            .where(Node.kb_id == kb_id, Node.deleted_at.is_(None))
        )
        query = (
            select(Node.title)
            .join(File, File.node_id == Node.id)
            .where(Node.id.in_(node_ids), Node.deleted_at.is_(None), File.sha256.in_(live))
            .order_by(Node.title)
        )
        return list(await self._session.scalars(query))
