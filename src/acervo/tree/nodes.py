import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import ConflictError, NotFoundError, ValidationError
from acervo.store.models import Node
from acervo.store.repositories import (
    key_between,
    last_sort,
    live_folder,
    lock_kb,
    sibling_title_taken,
    siblings,
    sort_key,
    upwards,
)
from acervo.store.repositories import paths as paths  # where tree.search reads it

# Files come from an upload, not from here.
CREATABLE = ("folder", "page")


async def live_node(session: AsyncSession, node_id: uuid.UUID) -> Node:
    # populate_existing: trash and restore update rows in bulk, behind the identity map.
    node = await session.get(Node, node_id, populate_existing=True)
    if node is None or node.deleted_at is not None:
        raise NotFoundError(f"node {node_id} not found")
    return node


def _title(title: str) -> str:
    # Collapsed as link targets are, so `[[Foo  Bar]]` resolves to a page named "Foo  Bar".
    title = " ".join(title.split())
    if not title:
        raise ValidationError("a title cannot be empty")
    return title


async def ensure_title_free(
    session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None, kind: str, title: str
) -> None:
    if await sibling_title_taken(session, kb_id, parent_id, kind, title):
        raise ConflictError("já existe", {"title": title})


async def create(session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None, kind: str, title: str) -> Node:
    if kind not in CREATABLE:
        raise ValidationError(f"cannot create a node of kind {kind!r}")
    title = _title(title)
    await lock_kb(session, kb_id)
    await live_folder(session, kb_id, parent_id)
    await ensure_title_free(session, kb_id, parent_id, kind, title)
    node = Node(
        kb_id=kb_id,
        parent_id=parent_id,
        kind=kind,
        title=title,
        sort=key_between(await last_sort(session, kb_id, parent_id), None),
    )
    session.add(node)
    await session.flush()
    return node


async def children(session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None) -> list[Node]:
    await live_folder(session, kb_id, parent_id)
    query = select(Node).where(*siblings(kb_id, parent_id)).order_by(sort_key(), Node.id)
    return list(await session.scalars(query))


async def rename(session: AsyncSession, node_id: uuid.UUID, title: str) -> Node:
    node = await live_node(session, node_id)
    title = _title(title)
    if title.lower() != node.title.lower():
        await ensure_title_free(session, node.kb_id, node.parent_id, node.kind, title)
    node.title = title
    await session.flush()
    return node


async def move(
    session: AsyncSession, node_id: uuid.UUID, parent_id: uuid.UUID | None, before_id: uuid.UUID | None = None
) -> Node:
    """Puts the node in `parent_id` just before the sibling `before_id`, or last when it is None."""
    node = await live_node(session, node_id)
    await live_folder(session, node.kb_id, parent_id)
    if parent_id is not None and node.id in await _ancestors(session, parent_id):
        raise ValidationError("a folder cannot move into itself or into a folder inside it")
    if parent_id != node.parent_id:
        await ensure_title_free(session, node.kb_id, parent_id, node.kind, node.title)

    others = [*siblings(node.kb_id, parent_id), Node.id != node.id]
    if before_id is None:
        previous = await session.scalar(select(func.max(sort_key())).where(*others))
        node.sort = key_between(previous, None)
    else:
        before = await live_node(session, before_id)
        if before.id == node.id or before.kb_id != node.kb_id or before.parent_id != parent_id:
            raise ValidationError(f"node {before_id} is not a sibling at the destination")
        previous = await session.scalar(select(func.max(sort_key())).where(*others, sort_key() < before.sort))
        node.sort = key_between(previous, before.sort)
    node.parent_id = parent_id
    await session.flush()
    return node


async def _ancestors(session: AsyncSession, node_id: uuid.UUID) -> set[uuid.UUID]:
    return set(await session.scalars(select(upwards([node_id]).c.id)))
