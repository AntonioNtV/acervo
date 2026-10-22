import uuid

from sqlalchemy import CTE, ColumnElement, exists, func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import NotFoundError, ValidationError
from acervo.store.models import Base, Kb, Node

DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


async def get[M: Base](session: AsyncSession, model: type[M], id: uuid.UUID) -> M:
    row = await session.get(model, id)
    if row is None:
        raise NotFoundError(f"{model.__tablename__} {id} not found")
    return row


async def lock_kb(session: AsyncSession, kb_id: uuid.UUID) -> None:
    """One writer per base until the transaction ends, so checks such as "já existe" hold until the write."""
    await session.execute(select(func.pg_advisory_xact_lock(int.from_bytes(kb_id.bytes[:8], signed=True))))


async def live_folder(session: AsyncSession, kb_id: uuid.UUID, folder_id: uuid.UUID | None) -> None:
    """The live base, and the live folder of it when `folder_id` is given (None is the base's root)."""
    # populate_existing: trash and restore update rows in bulk, behind the identity map.
    kb = await session.get(Kb, kb_id, populate_existing=True)
    if kb is None or kb.deleted_at is not None:
        raise NotFoundError(f"kb {kb_id} not found")
    if folder_id is None:
        return
    folder = await session.get(Node, folder_id, populate_existing=True)
    if folder is None or folder.deleted_at is not None:
        raise NotFoundError(f"node {folder_id} not found")
    if folder.kb_id != kb_id or folder.kind != "folder":
        raise ValidationError("a pasta não está nesta base")


def upwards(node_ids: list[uuid.UUID]) -> CTE:
    """Each start node and its ancestors, with their distance from the start."""
    up = (
        select(Node.id.label("start_id"), Node.id, Node.parent_id, Node.title, literal(0).label("depth"))
        .where(Node.id.in_(node_ids))
        .cte("up", recursive=True)
    )
    return up.union_all(
        select(up.c.start_id, Node.id, Node.parent_id, Node.title, up.c.depth + 1).join(Node, Node.id == up.c.parent_id)
    )


async def paths(session: AsyncSession, node_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Each node's path: the titles from the root down to it, joined by "/"."""
    if not node_ids:
        return {}
    up = upwards(node_ids)
    joined = func.string_agg(up.c.title, aggregate_order_by(literal("/"), up.c.depth.desc()))
    rows = await session.execute(select(up.c.start_id, joined).group_by(up.c.start_id))
    return {start_id: joined_path for start_id, joined_path in rows}


async def path(session: AsyncSession, node_id: uuid.UUID) -> str:
    found = await paths(session, [node_id])
    if node_id not in found:
        raise NotFoundError(f"node {node_id} not found")
    return found[node_id]


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
