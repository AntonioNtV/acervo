import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import NotFoundError, ValidationError
from acervo.store.models import FileVersion, Kb, Node, PageVersion
from acervo.tree.search import contains


@dataclass
class KbSummary:
    kb: Kb
    pages: int
    files: int
    last_edit: datetime


def _name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("a base needs a name")
    return name


async def _kb(session: AsyncSession, kb_id: uuid.UUID, trashed: bool = False) -> Kb:
    kb = await session.get(Kb, kb_id, populate_existing=True)
    if kb is None or (kb.deleted_at is not None) != trashed:
        raise NotFoundError(f"kb {kb_id} not found")
    return kb


async def list_kbs(session: AsyncSession, name: str = "") -> list[KbSummary]:
    """Live bases, most recently edited first."""
    counts = (
        select(
            Node.kb_id,
            func.count().filter(Node.kind == "page").label("pages"),
            func.count().filter(Node.kind == "file").label("files"),
        )
        .where(Node.deleted_at.is_(None))
        .group_by(Node.kb_id)
        .subquery()
    )
    edits = union_all(
        select(Kb.id.label("kb_id"), Kb.updated_at),
        select(Node.kb_id, Node.updated_at),
        select(Node.kb_id, PageVersion.updated_at).join(Node, Node.id == PageVersion.node_id),
        select(Node.kb_id, FileVersion.updated_at).join(Node, Node.id == FileVersion.node_id),
    ).subquery()
    last_edits = select(edits.c.kb_id, func.max(edits.c.updated_at).label("at")).group_by(edits.c.kb_id).subquery()
    query = (
        select(Kb, func.coalesce(counts.c.pages, 0), func.coalesce(counts.c.files, 0), last_edits.c.at)
        .outerjoin(counts, counts.c.kb_id == Kb.id)
        .join(last_edits, last_edits.c.kb_id == Kb.id)
        .where(Kb.deleted_at.is_(None))
        .order_by(last_edits.c.at.desc(), Kb.name)
    )
    if name.strip():
        query = query.where(contains(Kb.name, name.strip()))
    rows = await session.execute(query.execution_options(populate_existing=True))
    return [KbSummary(*row) for row in rows]


async def create_kb(session: AsyncSession, name: str, description: str = "") -> Kb:
    kb = Kb(name=_name(name), description=description.strip())
    session.add(kb)
    await session.flush()
    return kb


async def update_kb(
    session: AsyncSession, kb_id: uuid.UUID, name: str | None = None, description: str | None = None
) -> Kb:
    kb = await _kb(session, kb_id)
    if name is not None:
        kb.name = _name(name)
    if description is not None:
        kb.description = description.strip()
    await session.flush()
    return kb


async def trash_kb(session: AsyncSession, kb_id: uuid.UUID) -> Kb:
    """The whole base goes to the global trash; its nodes keep their own state, so it comes back intact."""
    kb = await _kb(session, kb_id)
    kb.deleted_at = func.now()
    await session.flush()
    await session.refresh(kb)
    return kb


async def list_trashed_kbs(session: AsyncSession) -> list[Kb]:
    query = select(Kb).where(Kb.deleted_at.is_not(None)).order_by(Kb.deleted_at.desc())
    return list(await session.scalars(query.execution_options(populate_existing=True)))


async def restore_kb(session: AsyncSession, kb_id: uuid.UUID) -> Kb:
    kb = await _kb(session, kb_id, trashed=True)
    kb.deleted_at = None
    await session.flush()
    return kb
