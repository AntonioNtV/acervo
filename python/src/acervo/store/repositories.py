import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import NotFoundError
from acervo.store.models import Base, Node


async def get[M: Base](session: AsyncSession, model: type[M], id: uuid.UUID) -> M:
    row = await session.get(model, id)
    if row is None:
        raise NotFoundError(f"{model.__tablename__} {id} not found")
    return row


async def sibling_title_taken(
    session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None, kind: str, title: str
) -> bool:
    """The check behind the live-sibling unique index, to refuse with "já existe" before the insert fails."""
    parent = Node.parent_id.is_(None) if parent_id is None else Node.parent_id == parent_id
    query = select(
        exists().where(
            Node.kb_id == kb_id,
            parent,
            Node.kind == kind,
            func.lower(Node.title) == func.lower(title),
            Node.deleted_at.is_(None),
        )
    )
    return bool(await session.scalar(query))
