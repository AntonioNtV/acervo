from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.db.models import Account, Kb, Node, PageVersion
from acervo.repositories.follow import FollowRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.notification import Notification
from acervo.services.digest_service import DigestService
from acervo.services.mailer import FakeMailer, MailTemplate, Unsubscribe

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeTree = Callable[..., Awaitable[Any]]

# 8:00 in São Paulo (UTC-3), 20:00 in Tokyo; far from the real clock, so `make_tree`'s own versions fall outside.
NOW = datetime(2040, 3, 10, 11, 0, tzinfo=UTC)
# Inside the previous local day of São Paulo, 9 March.
YESTERDAY = datetime(2040, 3, 9, 15, 0, tzinfo=UTC)
TREE = ["Renovação.md", "Glossário.md", "Sinistro.md"]


@pytest.fixture
async def entered(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[UnitOfWork]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield uow


@pytest.fixture
def digests(entered: UnitOfWork, fake_mailer: FakeMailer) -> DigestService:
    return DigestService(entered, fake_mailer)


async def _account(
    session: AsyncSession, make_account: MakeAccount, email: str, name: str, timezone: str = "America/Sao_Paulo"
) -> UUID:
    account = await make_account(email=email, name=name)
    row = await session.get_one(Account, account.id)
    row.notify_followed, row.timezone = True, timezone
    await session.flush()
    return account.id


@pytest.fixture
async def ana(session: AsyncSession, make_account: MakeAccount) -> UUID:
    return await _account(session, make_account, "ana@example.com", "Ana")


@pytest.fixture
async def bruno(session: AsyncSession, make_account: MakeAccount) -> UUID:
    return await _account(session, make_account, "bruno@example.com", "Bruno Lima", "Asia/Tokyo")


async def _save(
    session: AsyncSession, page: Node, author: UUID | None, at: datetime = YESTERDAY, author_known: bool = True
) -> None:
    version = PageVersion(
        node_id=page.id, markdown=f"# {page.title}\n", author_id=author, created_at=at, author_known=author_known
    )
    session.add(version)
    await session.flush()


async def test_due_by_time_zone(
    digests: DigestService, session: AsyncSession, make_account: MakeAccount, ana: UUID, bruno: UUID
) -> None:
    off = await make_account(email="carla@example.com", name="Carla")
    sent = await _account(session, make_account, "davi@example.com", "Davi")
    (await session.get_one(Account, sent)).digest_sent_on = date(2040, 3, 10)
    await session.flush()

    assert await digests.due(NOW) == [ana]
    # 23:00 UTC is 8:00 of 11 March in Tokyo and 20:00 in São Paulo.
    assert await digests.due(datetime(2040, 3, 10, 23, 0, tzinfo=UTC)) == [bruno]
    # 07:00 in São Paulo.
    assert await digests.due(datetime(2040, 3, 10, 10, 0, tzinfo=UTC)) == []
    assert off.id not in await digests.due(NOW)


async def test_lists_the_followed_pages_others_changed_with_authors_and_base(
    digests: DigestService,
    session: AsyncSession,
    make_tree: MakeTree,
    fake_mailer: FakeMailer,
    ana: UUID,
    bruno: UUID,
) -> None:
    tree = await make_tree(TREE, name="Jurídico")
    follows = FollowRepository(session)
    for path in TREE:
        await follows.follow(ana, tree[path].id)
    await _save(session, tree["Glossário.md"], ana)
    await _save(session, tree["Glossário.md"], bruno)
    await _save(session, tree["Renovação.md"], None)
    # Sinistro changed only the day before yesterday.
    await _save(session, tree["Sinistro.md"], bruno, datetime(2040, 3, 9, 2, 0, tzinfo=UTC))

    await digests.send(ana, NOW)

    [mail] = fake_mailer.sent
    assert (mail.to, mail.template, mail.language) == ("ana@example.com", MailTemplate.DIGEST, "pt-BR")
    assert mail.values == {
        "count": "2",
        "pages": "Glossário\tVocê e Bruno Lima\tJurídico\nRenovação\tConta excluída\tJurídico",
    }
    assert mail.unsubscribe == Unsubscribe(ana, Notification.FOLLOWED)
    assert (await session.get_one(Account, ana, populate_existing=True)).digest_sent_on == date(2040, 3, 10)


async def test_a_version_saved_before_authors_were_kept_adds_no_name(
    digests: DigestService, session: AsyncSession, make_tree: MakeTree, fake_mailer: FakeMailer, ana: UUID, bruno: UUID
) -> None:
    tree = await make_tree(TREE, name="Jurídico")
    for path in ("Glossário.md", "Renovação.md"):
        await FollowRepository(session).follow(ana, tree[path].id)
    await _save(session, tree["Glossário.md"], None, author_known=False)
    await _save(session, tree["Glossário.md"], bruno)
    await _save(session, tree["Renovação.md"], None, author_known=False)

    await digests.send(ana, NOW)

    [mail] = fake_mailer.sent
    assert mail.values["pages"] == "Glossário\tBruno Lima\tJurídico\nRenovação\t\tJurídico"


@pytest.mark.parametrize("case", ["only_mine", "page_trashed", "base_trashed", "unreadable", "toggle_off"])
async def test_sends_nothing(
    case: str,
    digests: DigestService,
    session: AsyncSession,
    make_tree: MakeTree,
    fake_mailer: FakeMailer,
    ana: UUID,
    bruno: UUID,
) -> None:
    organization = None
    if case == "unreadable":
        personal = await OrganizationRepository(session).get_by(personal_of=bruno)
        assert personal is not None
        organization = personal.id
    tree = await make_tree(TREE, organization=organization)
    page = tree["Glossário.md"]
    await FollowRepository(session).follow(ana, page.id)
    await _save(session, page, ana if case == "only_mine" else bruno)
    if case == "page_trashed":
        page.deleted_at = YESTERDAY
    if case == "base_trashed":
        (await session.get_one(Kb, tree.kb.id)).deleted_at = YESTERDAY
    if case == "toggle_off":
        (await session.get_one(Account, ana)).notify_followed = False
    await session.flush()

    await digests.send(ana, NOW)

    assert fake_mailer.sent == []
    sent_on = (await session.get_one(Account, ana, populate_existing=True)).digest_sent_on
    assert sent_on == (None if case == "toggle_off" else date(2040, 3, 10))


async def test_one_digest_a_day(
    digests: DigestService, session: AsyncSession, make_tree: MakeTree, fake_mailer: FakeMailer, ana: UUID, bruno: UUID
) -> None:
    tree = await make_tree(TREE)
    await FollowRepository(session).follow(ana, tree["Glossário.md"].id)
    await _save(session, tree["Glossário.md"], bruno)

    for account_id in await digests.due(NOW):
        await digests.send(account_id, NOW)
    for account_id in await digests.due(NOW):
        await digests.send(account_id, NOW)
    await digests.send(ana, NOW)
    await digests.send(uuid4(), NOW)

    assert [mail.to for mail in fake_mailer.sent] == ["ana@example.com"]


async def test_a_failed_mail_gives_the_day_back(
    digests: DigestService, session: AsyncSession, make_tree: MakeTree, fake_mailer: FakeMailer, ana: UUID, bruno: UUID
) -> None:
    tree = await make_tree(TREE)
    await FollowRepository(session).follow(ana, tree["Glossário.md"].id)
    await _save(session, tree["Glossário.md"], bruno)
    send = fake_mailer.send

    async def down(*args: object, **kwargs: object) -> None:
        raise ConnectionError("smtp down")

    fake_mailer.send = down  # type: ignore[method-assign]
    with pytest.raises(ConnectionError):
        await digests.send(ana, NOW)
    fake_mailer.send = send  # type: ignore[method-assign]
    await digests.send(ana, NOW)

    assert [mail.to for mail in fake_mailer.sent] == ["ana@example.com"]
