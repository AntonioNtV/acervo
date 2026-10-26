from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.core.errors import CodeInvalid, InvalidCredentials, TooManyAttempts
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, SignIn
from acervo.schemas.security import PendingSignIn, TwoFactorStart
from acervo.services.auth_service import AuthService
from acervo.services.mailer import FakeMailer, MailTemplate
from acervo.services.session_service import SessionService
from acervo.services.two_factor_service import TwoFactorService
from acervo.services.whatsapp import FakeWhatsApp

MakeAccount = Callable[..., Awaitable[AccountRead]]
PASSWORD = "senha-de-teste"
RIGHT = SignIn(email="ana@example.com", password=PASSWORD)


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def entered(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[UnitOfWork]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield uow


@pytest.fixture
def auth(entered: UnitOfWork, clock: Clock, fake_mailer: FakeMailer, fake_whatsapp: FakeWhatsApp) -> AuthService:
    return AuthService(entered, SessionService(entered, 30, clock), fake_mailer, fake_whatsapp, "pt_BR", clock)


@pytest.fixture
def two_factor(
    entered: UnitOfWork, clock: Clock, fake_mailer: FakeMailer, fake_whatsapp: FakeWhatsApp
) -> TwoFactorService:
    return TwoFactorService(entered, fake_mailer, fake_whatsapp, "pt_BR", clock)


@pytest.fixture
async def ana(make_account: MakeAccount, two_factor: TwoFactorService) -> AccountRead:
    """An account with two-step verification by email."""
    account = await make_account(email="ana@example.com", password=PASSWORD)
    return await two_factor.start(account.id, TwoFactorStart(method="email"), None)


async def pend(auth: AuthService) -> str:
    """Signs in with the right password; gives the pending sign-in's token."""
    pending, token = await auth.sign_in(RIGHT, None)
    assert isinstance(pending, PendingSignIn)
    return token


def last_code(mailer: FakeMailer) -> str:
    mail = mailer.sent[-1]
    assert mail.template == MailTemplate.LOGIN_CODE
    return mail.values["code"]


async def test_the_pending_sign_in_expires_after_10_minutes(
    auth: AuthService, ana: AccountRead, fake_mailer: FakeMailer, clock: Clock
) -> None:
    token = await pend(auth)
    clock.advance(timedelta(minutes=10, seconds=1))

    with pytest.raises(CodeInvalid):
        await auth.finish_two_factor(token, last_code(fake_mailer), None)


async def test_five_wrong_codes_end_the_pending_sign_in(
    auth: AuthService, ana: AccountRead, fake_mailer: FakeMailer
) -> None:
    token = await pend(auth)
    code = last_code(fake_mailer)
    for _ in range(5):
        with pytest.raises(CodeInvalid):
            await auth.finish_two_factor(token, "000000", None)

    with pytest.raises(CodeInvalid):
        await auth.finish_two_factor(token, code, None)


async def test_no_new_code_once_the_five_tries_are_spent(
    auth: AuthService, ana: AccountRead, fake_mailer: FakeMailer, clock: Clock
) -> None:
    token = await pend(auth)
    for _ in range(5):
        with pytest.raises(CodeInvalid):
            await auth.finish_two_factor(token, "000000", None)
    clock.advance(timedelta(seconds=61))
    sent = len(fake_mailer.sent)

    with pytest.raises(CodeInvalid):
        await auth.resend_two_factor(token, to_email=False)
    assert len(fake_mailer.sent) == sent


async def test_wrong_codes_count_toward_the_lockout_with_wrong_passwords(auth: AuthService, ana: AccountRead) -> None:
    for _ in range(3):
        with pytest.raises(InvalidCredentials):
            await auth.sign_in(SignIn(email="ana@example.com", password="errada-errada"), None)
    token = await pend(auth)
    for _ in range(2):
        with pytest.raises(CodeInvalid):
            await auth.finish_two_factor(token, "000000", None)

    with pytest.raises(TooManyAttempts):
        await auth.sign_in(RIGHT, None)


async def test_a_whatsapp_code_can_come_by_email_instead(
    auth: AuthService,
    two_factor: TwoFactorService,
    ana: AccountRead,
    fake_mailer: FakeMailer,
    fake_whatsapp: FakeWhatsApp,
    clock: Clock,
) -> None:
    await two_factor.start(ana.id, TwoFactorStart(method="whatsapp", phone="+5511912345678"), None)
    on = await two_factor.confirm(ana.id, fake_whatsapp.sent[-1].code, None)
    pending, token = await auth.sign_in(RIGHT, None)
    assert (on.two_factor, pending) == (
        "whatsapp",
        PendingSignIn(method="whatsapp", destination="+55 •• ••••-5678"),
    )
    whatsapp_code = fake_whatsapp.sent[-1].code

    clock.advance(timedelta(seconds=61))
    by_email = await auth.resend_two_factor(token, to_email=True)
    email_code = last_code(fake_mailer)

    assert by_email == PendingSignIn(method="email", destination="a•••@example.com")
    if whatsapp_code != email_code:
        with pytest.raises(CodeInvalid):
            await auth.finish_two_factor(token, whatsapp_code, None)
    account, session = await auth.finish_two_factor(token, email_code, None)
    assert (account.id, bool(session)) == (ana.id, True)
