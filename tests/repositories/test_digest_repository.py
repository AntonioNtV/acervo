from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models import Account, PageVersion
from acervo.repositories.digest import DigestRepository
from acervo.repositories.follow import FollowRepository
from acervo.schemas.account import AccountRead
from acervo.schemas.follow import FollowCreate

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeTree = Callable[..., Awaitable[Any]]

# 8:00 in São Paulo (UTC-3), 20:00 in Tokyo.
NOW = datetime(2040, 3, 10, 11, 0, tzinfo=UTC)
TODAY = date(2040, 3, 10)


async def _account(session: AsyncSession, make_account: MakeAccount, email: str, **columns: Any) -> UUID:
    account = await make_account(email=email)
    row = await session.get_one(Account, account.id)
    row.notify_followed = True
    for name, value in columns.items():
        setattr(row, name, value)
    await session.flush()
    return account.id


async def test_due_is_8_local_with_the_digest_on_and_none_sent_today(
    session: AsyncSession, make_account: MakeAccount
) -> None:
    ana = await _account(session, make_account, "ana@example.com")
    await _account(session, make_account, "bia@example.com", timezone="Asia/Tokyo")
    await _account(session, make_account, "caio@example.com", notify_followed=False)
    await _account(session, make_account, "duda@example.com", digest_sent_on=TODAY)

    assert await DigestRepository(session).due(NOW) == [ana]


async def test_claim_marks_the_day_once_and_release_gives_it_back(
    session: AsyncSession, make_account: MakeAccount
) -> None:
    digests = DigestRepository(session)
    ana = await _account(session, make_account, "ana@example.com", digest_sent_on=date(2040, 3, 1))

    assert await digests.claim(ana, TODAY)
    assert not await digests.claim(ana, TODAY)
    await digests.release(ana, TODAY, date(2040, 3, 1))

    account = await digests.get_by(id=ana)
    assert account is not None and account.digest_sent_on == date(2040, 3, 1)
    assert await digests.claim(ana, TODAY)


async def test_changes_are_the_followed_live_pages_saved_in_the_window(
    session: AsyncSession, make_account: MakeAccount, make_tree: MakeTree, default_account_id: UUID
) -> None:
    tree = await make_tree(["Renovação.md", "Glossário.md", "Sinistro.md"])
    follows = FollowRepository(session)
    for path in ("Renovação.md", "Glossário.md"):
        await follows.follow(FollowCreate(account_id=default_account_id, node_id=tree[path].id))
    tree["Glossário.md"].deleted_at = NOW
    yesterday = datetime(2040, 3, 9, 15, 0, tzinfo=UTC)
    for path, at in (
        ("Renovação.md", yesterday),
        ("Renovação.md", NOW),
        ("Glossário.md", yesterday),
        ("Sinistro.md", yesterday),
    ):
        session.add(PageVersion(node_id=tree[path].id, markdown="x\n", author_id=default_account_id, created_at=at))
    await session.flush()

    changes = await DigestRepository(session).changes(
        default_account_id, datetime(2040, 3, 9, 3, 0, tzinfo=UTC), datetime(2040, 3, 10, 3, 0, tzinfo=UTC)
    )

    assert [(c.title, c.base, c.author_known) for c in changes] == [("Renovação", tree.kb.name, True)]
