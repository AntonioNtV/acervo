from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
DAYS = 30
START = datetime(2026, 10, 26, 9, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def sessions(uow: UnitOfWork, session: AsyncSession, clock: Clock) -> AsyncIterator[SessionService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield SessionService(uow, DAYS, clock)


async def test_a_session_resolves_to_its_account(sessions: SessionService, make_account: MakeAccount) -> None:
    ana = await make_account()

    token = await sessions.create(ana.id, "Firefox")

    assert await sessions.resolve(token) == ana
    assert await sessions.resolve("not-a-token") is None


async def test_a_session_expires_days_after_its_last_request(
    sessions: SessionService, make_account: MakeAccount, clock: Clock
) -> None:
    token = await sessions.create((await make_account()).id, None)

    clock.now = START + timedelta(days=DAYS - 1)
    assert await sessions.resolve(token) is not None
    clock.now = START + timedelta(days=2 * DAYS - 2)
    assert await sessions.resolve(token) is not None
    clock.now = START + timedelta(days=3 * DAYS)
    assert await sessions.resolve(token) is None


async def test_renewal_writes_at_most_once_a_minute(
    sessions: SessionService, make_account: MakeAccount, clock: Clock, uow: UnitOfWork
) -> None:
    ana = await make_account()
    token = await sessions.create(ana.id, None)
    row = await uow.sessions.get_by(account_id=ana.id)
    assert row is not None

    clock.now = START + timedelta(seconds=30)
    await sessions.resolve(token)
    assert (await uow.sessions.get(row.id)).last_seen_at == START

    clock.now = START + timedelta(seconds=90)
    await sessions.resolve(token)
    renewed = await uow.sessions.get(row.id)
    assert (renewed.last_seen_at, renewed.expires_at) == (clock.now, clock.now + timedelta(days=DAYS))


async def test_an_ended_session_resolves_to_nothing(sessions: SessionService, make_account: MakeAccount) -> None:
    ana = await make_account()
    token = await sessions.create(ana.id, None)

    await sessions.end(token)

    assert await sessions.resolve(token) is None


async def test_end_all_keeps_the_excepted_session(sessions: SessionService, make_account: MakeAccount) -> None:
    ana = await make_account()
    bia = await make_account(email="bia@example.com")
    here, elsewhere, other = (
        await sessions.create(ana.id, None),
        await sessions.create(ana.id, None),
        await sessions.create(bia.id, None),
    )

    await sessions.end_all(ana.id, except_token=here)

    assert await sessions.resolve(here) == ana
    assert await sessions.resolve(elsewhere) is None
    assert await sessions.resolve(other) == bia
    await sessions.end_all(ana.id)
    assert await sessions.resolve(here) is None


@pytest.mark.parametrize(
    ("user_agent", "named"),
    [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 "
            "Safari/537.36 Edg/130.0.0.0",
            ("Edge", "Windows"),
        ),
        ("Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0", ("Firefox", "Linux")),
        (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 "
            "Mobile Safari/537.36",
            ("Chrome", "Android"),
        ),
        ("curl/8.7.1", (None, None)),
        (None, (None, None)),
    ],
)
def test_device_names_the_browser_and_system(user_agent: str | None, named: tuple[str | None, str | None]) -> None:
    assert device(user_agent) == named


async def test_listing_shows_live_sessions_with_their_method(
    sessions: SessionService, make_account: MakeAccount, clock: Clock, uow: UnitOfWork
) -> None:
    ana = await make_account()
    await sessions.create(ana.id, None, "google")
    clock.now = START + timedelta(days=DAYS + 1)
    await sessions.create(ana.id, None)
    current = await uow.sessions.get_by(account_id=ana.id, method="password")
    assert current is not None

    listed = await sessions.of_account(ana.id, current.id)

    assert [(row.method, row.current) for row in listed] == [("password", True)]
