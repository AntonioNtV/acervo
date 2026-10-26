from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import CodeInvalid, EmailTaken, InvalidCredentials, TooManyAttempts
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, EmailCodeIn, ResetConfirm, SignIn, SignUp
from acervo.services.auth_service import AuthService
from acervo.services.mailer import FakeMailer
from acervo.services.session_service import SessionService

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
        yield AuthService(uow, SessionService(uow, 30, clock), fake_mailer, "http://app.test", clock)


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
    token = fake_mailer.sent[-1].values["link"].rsplit("/", 1)[-1]

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
