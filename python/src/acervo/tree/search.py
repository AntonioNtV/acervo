import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.store.models import Node
from acervo.tree.nodes import paths

LIMIT = 50


@dataclass
class SearchHit:
    node: Node
    path: str


def folded(text: ColumnElement[str]) -> ColumnElement[str]:
    """Lowercase and without accents, the same expression the trigram index holds."""
    return func.acervo.immutable_unaccent(func.lower(text))


def contains(column: ColumnElement[str], query: str) -> ColumnElement[bool]:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return folded(column).like(func.concat("%", folded(literal(escaped)), "%"), escape="\\")


async def search(session: AsyncSession, kb_id: uuid.UUID, query: str) -> list[SearchHit]:
    """The person's name search (rule 2 of CLAUDE.md): titles only, never an agent's way to find content."""
    query = query.strip()
    if not query:
        return []
    closeness = func.similarity(folded(Node.title), folded(literal(query)))
    rows = (
        select(Node)
        .where(Node.kb_id == kb_id, Node.deleted_at.is_(None), contains(Node.title, query))
        .order_by(closeness.desc(), Node.title)
        .limit(LIMIT)
    )
    nodes = list(await session.scalars(rows))
    found = await paths(session, [node.id for node in nodes])
    return [SearchHit(node, found[node.id]) for node in nodes]
