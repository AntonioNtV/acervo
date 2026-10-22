import uuid

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import NotFoundError
from acervo.store.models import Base, Node

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


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


def key_between(before: str | None, after: str | None) -> str:
    """A sort key strictly between two neighbours' keys (None is an open end), so placing an item writes one row."""
    return _midpoint(before or "", after)


def _midpoint(low: str, high: str | None) -> str:
    if high is not None:
        shared = 0
        while (low[shared] if shared < len(low) else "0") == high[shared]:
            shared += 1
        if shared:
            return high[:shared] + _midpoint(low[shared:], high[shared:])
    low_digit = DIGITS.index(low[0]) if low else 0
    high_digit = DIGITS.index(high[0]) if high is not None else len(DIGITS)
    if high_digit - low_digit > 1:
        return DIGITS[(low_digit + high_digit) // 2]
    if high is not None and len(high) > 1:
        return high[0]
    return DIGITS[low_digit] + _midpoint(low[1:], None)


def sort_key() -> ColumnElement[str]:
    # Keys compare byte by byte, as `key_between` builds them, whatever the database's collation.
    return Node.sort.collate("C")


def siblings(kb_id: uuid.UUID, parent_id: uuid.UUID | None) -> list[ColumnElement[bool]]:
    parent = Node.parent_id.is_(None) if parent_id is None else Node.parent_id == parent_id
    return [Node.kb_id == kb_id, parent, Node.deleted_at.is_(None)]


async def last_sort(session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None) -> str | None:
    return await session.scalar(select(func.max(sort_key())).where(*siblings(kb_id, parent_id)))
