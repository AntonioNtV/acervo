import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.store.models import PageDraft


async def get(session: AsyncSession, node_id: uuid.UUID) -> PageDraft | None:
    return await session.scalar(select(PageDraft).where(PageDraft.node_id == node_id))


async def put(session: AsyncSession, node_id: uuid.UUID, markdown: str, base_version_id: uuid.UUID) -> PageDraft:
    """The page's single draft, replaced on every autosave. Never a version."""
    draft = await get(session, node_id)
    if draft is None:
        draft = PageDraft(node_id=node_id, markdown=markdown, base_version_id=base_version_id)
        session.add(draft)
    else:
        draft.markdown, draft.base_version_id = markdown, base_version_id
    await session.flush()
    await session.refresh(draft)
    return draft


async def discard(session: AsyncSession, node_id: uuid.UUID) -> None:
    await session.execute(delete(PageDraft).where(PageDraft.node_id == node_id))
