"""The shared helpers under their old names, for the concept packages until cards 03-05 move them onto the
repositories."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.base import Base
from acervo.domain.sort_keys import key_between as key_between
from acervo.errors import NotFoundError
from acervo.repositories.kb import KbRepository
from acervo.repositories.node import NodeRepository
from acervo.repositories.node import siblings as siblings
from acervo.repositories.node import sort_key as sort_key
from acervo.repositories.node import upwards as upwards


async def get[M: Base](session: AsyncSession, model: type[M], id: uuid.UUID) -> M:
    row = await session.get(model, id)
    if row is None:
        raise NotFoundError(f"{model.__tablename__} {id} not found")
    return row


async def lock_kb(session: AsyncSession, kb_id: uuid.UUID) -> None:
    await KbRepository(session).lock(kb_id)


async def live_folder(session: AsyncSession, kb_id: uuid.UUID, folder_id: uuid.UUID | None) -> None:
    await NodeRepository(session).live_folder(kb_id, folder_id)


async def paths(session: AsyncSession, node_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    return await NodeRepository(session).paths(node_ids)


async def path(session: AsyncSession, node_id: uuid.UUID) -> str:
    return await NodeRepository(session).path(node_id)


async def sibling_title_taken(
    session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None, kind: str, title: str
) -> bool:
    return await NodeRepository(session).title_taken(kb_id, parent_id, kind, title)


async def last_sort(session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None) -> str | None:
    return await NodeRepository(session).last_sort(kb_id, parent_id)
