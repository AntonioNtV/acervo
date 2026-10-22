import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import NotFoundError
from acervo.store.models import Node
from acervo.tree.nodes import ensure_title_free, key_between, last_sort, live_node, paths


@dataclass
class TrashItem:
    node: Node
    # Where it was when it was trashed.
    path: str


@dataclass
class Restored:
    node: Node
    # Its old folder was gone, so it came back at the base's root.
    to_root: bool


async def trash(session: AsyncSession, node_id: uuid.UUID) -> Node:
    """Hides the node and its whole live subtree; what was already in the trash keeps its own `trashed_with`."""
    node = await live_node(session, node_id)
    subtree = select(Node.id).where(Node.id == node.id).cte("subtree", recursive=True)
    subtree = subtree.union_all(
        select(Node.id).join(subtree, Node.parent_id == subtree.c.id).where(Node.deleted_at.is_(None))
    )
    await session.execute(
        update(Node)
        .where(Node.id.in_(select(subtree.c.id)))
        .values(deleted_at=func.now(), trashed_with=node.id)
        .execution_options(synchronize_session=False)
    )
    await session.refresh(node)
    return node


async def list_trash(session: AsyncSession, kb_id: uuid.UUID) -> list[TrashItem]:
    """One row per trashed root, most recent first."""
    query = select(Node).where(Node.kb_id == kb_id, Node.trashed_with == Node.id).order_by(Node.deleted_at.desc())
    nodes = list(await session.scalars(query.execution_options(populate_existing=True)))
    found = await paths(session, [node.id for node in nodes])
    return [TrashItem(node, found[node.id]) for node in nodes]


async def restore(session: AsyncSession, node_id: uuid.UUID) -> Restored:
    node = await session.get(Node, node_id, populate_existing=True)
    if node is None or node.trashed_with != node.id:
        raise NotFoundError(f"node {node_id} is not in the trash")
    parent_gone = node.parent_id is not None and (
        await session.scalar(select(Node.deleted_at.is_not(None)).where(Node.id == node.parent_id))
    )
    parent_id = None if parent_gone else node.parent_id
    await ensure_title_free(session, node.kb_id, parent_id, node.kind, node.title)
    if parent_gone:
        node.parent_id = None
        node.sort = key_between(await last_sort(session, node.kb_id, None), None)
        await session.flush()
    await session.execute(
        update(Node)
        .where(Node.trashed_with == node.id)
        .values(deleted_at=None, trashed_with=None)
        .execution_options(synchronize_session=False)
    )
    await session.refresh(node)
    return Restored(node, bool(parent_gone))
