import asyncio
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from acervo.core.errors import CodeInvalid, EmailNotVerified, EmailTaken, InvalidCredentials, TooManyAttempts
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, EmailCodeIn, ResetConfirm, SignIn, SignUp
from acervo.services import auth_service
from acervo.services.auth_service import CODE_TRIES, AuthService
from acervo.services.mailer import FakeMailer
from acervo.services.session_service import SessionService
from acervo.services.whatsapp import FakeWhatsApp

MakeAccount = Callable[..., Awaitable[AccountRead]]
PASSWORD = "senha-de-teste"


class Clock:
    def __init__(self) -> None:
        # Real time: `make_account` rows get the database's clock.
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def auth(
    uow: UnitOfWork, session: AsyncSession, clock: Clock, fake_mailer: FakeMailer
) -> AsyncIterator[AuthService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield AuthService(uow, SessionService(uow, 30, clock), fake_mailer, FakeWhatsApp(), "pt_BR", clock)


async def test_five_wrong_passwords_lock_the_email_for_15_minutes(
    auth: AuthService, make_account: MakeAccount, clock: Clock
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    wrong = SignIn(email="ANA@example.com", password="errada-errada")
    right = SignIn(email="ana@example.com", password=PASSWORD)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            await auth.sign_in(wrong, None)

    with pytest.raises(TooManyAttempts):
        await auth.sign_in(right, None)
    clock.advance(timedelta(minutes=14))
    with pytest.raises(TooManyAttempts):
        await auth.sign_in(right, None)
    clock.advance(timedelta(minutes=2))
    account, token = await auth.sign_in(right, None)
    assert (account.email, bool(token)) == ("ana@example.com", True)


async def test_a_password_reset_lifts_the_lock(
    auth: AuthService, make_account: MakeAccount, fake_mailer: FakeMailer
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            await auth.sign_in(SignIn(email="ana@example.com", password="errada-errada"), None)
    await auth.request_reset("ana@example.com")
    token = fake_mailer.sent[-1].values["link"]

    await auth.confirm_reset(ResetConfirm(token=token, password="nova-senha-longa"), None)
    account, _ = await auth.sign_in(SignIn(email="ana@example.com", password="nova-senha-longa"), None)
    assert account.email == "ana@example.com"


async def test_a_code_expires_after_10_minutes_and_after_5_wrong_tries(
    auth: AuthService, fake_mailer: FakeMailer, clock: Clock
) -> None:
    await auth.sign_up(SignUp(name="Ana", email="ana@example.com", password=PASSWORD))
    code = fake_mailer.sent[-1].values["code"]

    clock.advance(timedelta(minutes=11))
    with pytest.raises(CodeInvalid):
        await auth.verify_email(EmailCodeIn(email="ana@example.com", code=code), None)

    await auth.resend_code("ana@example.com")
    code = fake_mailer.sent[-1].values["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        with pytest.raises(CodeInvalid):
            await auth.verify_email(EmailCodeIn(email="ana@example.com", code=wrong), None)
    with pytest.raises(CodeInvalid):
        await auth.verify_email(EmailCodeIn(email="ana@example.com", code=code), None)

    clock.advance(timedelta(minutes=1))
    await auth.resend_code("ana@example.com")
    code = fake_mailer.sent[-1].values["code"]
    account, _ = await auth.verify_email(EmailCodeIn(email="ana@example.com", code=code), None)
    assert account.email_verified


async def test_a_reset_link_works_once(auth: AuthService, make_account: MakeAccount, fake_mailer: FakeMailer) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    await auth.request_reset("ana@example.com")
    token = fake_mailer.sent[-1].values["link"]

    await auth.confirm_reset(ResetConfirm(token=token, password="nova-senha-longa"), None)
    with pytest.raises(CodeInvalid):
        await auth.confirm_reset(ResetConfirm(token=token, password="outra-senha-longa"), None)

    account, _ = await auth.sign_in(SignIn(email="ana@example.com", password="nova-senha-longa"), None)
    assert account.email == "ana@example.com"


async def test_an_unconfirmed_account_frees_its_email_after_7_days(
    auth: AuthService, make_account: MakeAccount, clock: Clock
) -> None:
    stale = await make_account(email="ana@example.com", verified=False)
    data = SignUp(name="Ana Souza", email="Ana@example.com", password=PASSWORD)
    with pytest.raises(EmailTaken):
        await auth.sign_up(data)

    clock.advance(timedelta(days=8))
    account = await auth.sign_up(data)

    assert (account.id != stale.id, account.email, account.email_verified) == (True, "Ana@example.com", False)


async def test_spaced_wrong_passwords_lock_until_15_minutes_after_the_fifth(
    auth: AuthService, uow: UnitOfWork, make_account: MakeAccount, clock: Clock
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    wrong = SignIn(email="ana@example.com", password="errada-errada")
    right = SignIn(email="ana@example.com", password=PASSWORD)
    with pytest.raises(InvalidCredentials):
        await auth.sign_in(wrong, None)
    clock.advance(timedelta(minutes=20))
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            await auth.sign_in(wrong, None)
        clock.advance(timedelta(minutes=3))
    # The fifth was 3 minutes ago: locked until 12 minutes from now, a refused try not extending it.
    clock.advance(timedelta(minutes=6))
    with pytest.raises(TooManyAttempts):
        await auth.sign_in(wrong, None)
    clock.advance(timedelta(minutes=5))
    with pytest.raises(TooManyAttempts):
        await auth.sign_in(right, None)
    clock.advance(timedelta(minutes=2))

    account, _ = await auth.sign_in(right, None)
    assert account.email == "ana@example.com"
    # The failure 20 minutes before the others left the table with the next one.
    assert await uow.login_failures.count({"email_lower": "ana@example.com"}) == 5


async def test_parallel_wrong_tries_never_pass_the_limits(engine: AsyncEngine, fake_mailer: FakeMailer) -> None:
    # Separate connections that commit: on the test's one connection the tries could not race.
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = f"{uuid.uuid4().hex}@example.com"

    async def attempt(call: Callable[[AuthService], Awaitable[Any]]) -> Any:
        async with UnitOfWork(factory) as uow:
            return await call(AuthService(uow, SessionService(uow, 30), fake_mailer, FakeWhatsApp(), "pt_BR"))

    async def in_parallel(call: Callable[[AuthService], Awaitable[Any]]) -> list[str]:
        # 20 at once: NullPool opens a connection per try, and the server is shared with other worktrees.
        results = await asyncio.gather(*(attempt(call) for _ in range(20)), return_exceptions=True)
        return sorted(type(result).__name__ for result in results)

    await attempt(lambda auth: auth.sign_up(SignUp(name="Ana", email=email, password=PASSWORD)))
    code = fake_mailer.sent[-1].values["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    try:
        codes = await in_parallel(lambda auth: auth.verify_email(EmailCodeIn(email=email, code=wrong), None))
        passwords = await in_parallel(lambda auth: auth.sign_in(SignIn(email=email, password="errada-errada"), None))
        right = await asyncio.gather(
            attempt(lambda auth: auth.verify_email(EmailCodeIn(email=email, code=code), None)), return_exceptions=True
        )
        async with UnitOfWork(factory) as uow:
            account = await uow.accounts.by_email(email)
            assert account is not None
            live = await uow.email_codes.live(account.id, "verify_email")
    finally:
        async with UnitOfWork(factory) as uow:
            if (stored := await uow.accounts.by_email(email)) is not None:
                await uow.accounts.delete(stored.id)
            await uow.login_failures.clear(email)
            await uow.commit()

    assert codes == ["CodeInvalid"] * 20
    assert (live is not None and live.attempts, [type(r).__name__ for r in right]) == (CODE_TRIES, ["CodeInvalid"])
    assert passwords == ["InvalidCredentials"] * 5 + ["TooManyAttempts"] * 15


async def test_passwords_are_hashed_off_the_event_loop(auth: AuthService, monkeypatch: pytest.MonkeyPatch) -> None:
    threads: list[int] = []

    def spy(real: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: str) -> Any:
            threads.append(threading.get_ident())
            return real(*args)

        return call

    for name in ("hash_password", "verify_password"):
        monkeypatch.setattr(auth_service, name, spy(getattr(auth_service, name)))

    await auth.sign_up(SignUp(name="Ana", email="ana@example.com", password=PASSWORD))
    with pytest.raises(EmailNotVerified):
        await auth.sign_in(SignIn(email="ana@example.com", password=PASSWORD), None)

    assert len(threads) == 2
    assert threading.get_ident() not in threads


async def test_a_second_reset_within_a_minute_sends_nothing(
    auth: AuthService, make_account: MakeAccount, fake_mailer: FakeMailer, clock: Clock
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)

    await auth.request_reset("ana@example.com")
    clock.advance(timedelta(seconds=59))
    await auth.request_reset("ana@example.com")
    clock.advance(timedelta(seconds=2))
    await auth.request_reset("ana@example.com")

    assert len(fake_mailer.sent) == 2


async def test_a_new_password_ends_every_other_reset_link(
    auth: AuthService, make_account: MakeAccount, fake_mailer: FakeMailer, clock: Clock
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD)
    await auth.request_reset("ana@example.com")
    older = fake_mailer.sent[-1].values["link"]
    clock.advance(timedelta(minutes=2))
    await auth.request_reset("ana@example.com")

    await auth.confirm_reset(ResetConfirm(token=fake_mailer.sent[-1].values["link"], password="nova-senha-longa"), None)
    with pytest.raises(CodeInvalid):
        await auth.confirm_reset(ResetConfirm(token=older, password="outra-senha-longa"), None)


async def test_signing_in_to_a_stale_unconfirmed_account_frees_its_email(
    auth: AuthService, uow: UnitOfWork, make_account: MakeAccount, clock: Clock
) -> None:
    await make_account(email="ana@example.com", password=PASSWORD, verified=False)
    clock.advance(timedelta(days=8))

    with pytest.raises(InvalidCredentials):
        await auth.sign_in(SignIn(email="ana@example.com", password=PASSWORD), None)
    assert await uow.accounts.by_email("ana@example.com") is None
