from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models.node import Node
from acervo.db.models.page_follow import PageFollow
from acervo.db.models.page_version import PageVersion
from acervo.repositories.follow import FollowRepository
from tests.conftest import Tree


async def _count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(PageFollow)) or 0


async def test_follow_twice_keeps_one_row(
    session: AsyncSession, make_tree: Callable[..., Awaitable[Tree]], default_account_id: UUID
) -> None:
    tree = await make_tree(["Emissão de apólice.md"])
    follows, page = FollowRepository(session), tree["Emissão de apólice.md"]

    await follows.follow(default_account_id, page.id)
    await follows.follow(default_account_id, page.id)

    assert await follows.is_following(default_account_id, page.id)
    assert await _count(session) == 1


async def test_unfollow(
    session: AsyncSession, make_tree: Callable[..., Awaitable[Tree]], default_account_id: UUID
) -> None:
    tree = await make_tree(["Emissão de apólice.md"])
    follows, page = FollowRepository(session), tree["Emissão de apólice.md"]
    await follows.follow(default_account_id, page.id)

    await follows.unfollow(default_account_id, page.id)

    assert not await follows.is_following(default_account_id, page.id)


async def test_deleting_the_node_removes_the_follow(
    session: AsyncSession, make_tree: Callable[..., Awaitable[Tree]], default_account_id: UUID
) -> None:
    tree = await make_tree(["Emissão de apólice.md"])
    follows, page = FollowRepository(session), tree["Emissão de apólice.md"]
    await follows.follow(default_account_id, page.id)

    # Versions do not cascade with their page: they go first, as when a whole base is deleted.
    await session.execute(delete(PageVersion).where(PageVersion.node_id == page.id))
    await session.execute(delete(Node).where(Node.id == page.id))

    assert await _count(session) == 0
