import time
from collections.abc import AsyncIterator, Awaitable, Callable
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, AccountUpdate
from acervo.schemas.organization import InviteCreate, OrganizationRecord
from acervo.services.access_service import AccessService
from acervo.services.google_auth_service import GoogleAuthService
from acervo.services.google_client import GoogleClient, GoogleIdentity
from acervo.services.invite_service import InviteService
from acervo.services.mailer import FakeMailer
from acervo.services.session_service import SessionService

MakeAccount = Callable[..., Awaitable[AccountRead]]
MakeOrganization = Callable[..., Awaitable[OrganizationRecord]]
REDIRECT_URI = "http://localhost:5173/v1/auth/google/callback"


class FakeGoogle(GoogleClient):
    def __init__(self) -> None:
        super().__init__("client-id", "client-secret")
        self.person = GoogleIdentity(sub="google-1", email="Ana@Example.com", email_verified=True, name="Ana Google")

    async def identity(self, code: str, code_verifier: str, redirect_uri: str) -> GoogleIdentity:
        return self.person


@pytest.fixture
async def sessions(uow: UnitOfWork, session: AsyncSession) -> AsyncIterator[SessionService]:
    # Asks for `session` so it closes after this unit of work: its savepoint encloses the unit of work's.
    async with uow:
        yield SessionService(uow, 30)


@pytest.fixture
def service(uow: UnitOfWork, sessions: SessionService, fake_mailer: FakeMailer) -> GoogleAuthService:
    return GoogleAuthService(uow, sessions, FakeGoogle(), fake_mailer, "secret", REDIRECT_URI)


async def _continue(service: GoogleAuthService, next: str | None = "/kbs/1") -> tuple[str, str | None]:
    url, cookie = service.start(next)
    state = parse_qs(urlsplit(url).query)["state"][0]
    landing = await service.finish("code", state, cookie, "Firefox")
    return landing.path, landing.session_token


async def test_the_account_with_that_google_sub_signs_in(
    service: GoogleAuthService, sessions: SessionService, uow: UnitOfWork, make_account: MakeAccount
) -> None:
    ana = await make_account(email="other@example.com")
    await uow.accounts.update(ana.id, AccountUpdate(google_sub="google-1"))

    path, token = await _continue(service)

    assert path == "/kbs/1"
    signed_in = await sessions.resolve(token or "")
    assert signed_in is not None
    assert signed_in.id == ana.id


async def test_a_confirmed_account_with_that_email_is_linked(
    service: GoogleAuthService, sessions: SessionService, make_account: MakeAccount
) -> None:
    ana = await make_account()

    path, token = await _continue(service)

    assert path == "/kbs/1"
    signed_in = await sessions.resolve(token or "")
    assert signed_in is not None
    assert (signed_in.id, signed_in.has_google) == (ana.id, True)


async def test_an_unconfirmed_account_is_linked_after_its_password(
    service: GoogleAuthService, sessions: SessionService, make_account: MakeAccount
) -> None:
    ana = await make_account(verified=False, password="senha-de-teste")

    path, token = await _continue(service)

    assert token is None
    assert urlsplit(path).path == "/entrar/vincular"
    query = parse_qs(urlsplit(path).query)
    assert query["next"] == ["/kbs/1"]
    account, session_token = await service.link(query["token"][0], "senha-de-teste", "Firefox")
    assert (account.id, account.has_google, account.email_verified) == (ana.id, True, True)
    assert await sessions.resolve(session_token) == account


async def test_a_new_person_gets_a_confirmed_account(
    service: GoogleAuthService, sessions: SessionService, uow: UnitOfWork
) -> None:
    path, token = await _continue(service)

    assert path == "/kbs/1"
    account = await sessions.resolve(token or "")
    assert account is not None
    assert (account.email, account.name, account.email_verified, account.has_password) == (
        "Ana@Example.com",
        "Ana Google",
        True,
        False,
    )


@pytest.mark.parametrize("next", ["https://evil.example/kbs", "//evil.example/kbs", "/\\evil.example", None])
async def test_next_off_this_origin_falls_back_to_the_root(service: GoogleAuthService, next: str | None) -> None:
    path, _ = await _continue(service, next)

    assert path == "/"


async def test_a_stale_unconfirmed_account_gives_way_to_a_new_one(
    uow: UnitOfWork, sessions: SessionService, fake_mailer: FakeMailer, make_account: MakeAccount
) -> None:
    stale = await make_account(verified=False)
    in_8_days = GoogleAuthService(
        uow, sessions, FakeGoogle(), fake_mailer, "secret", REDIRECT_URI, lambda: time.time() + 8 * 24 * 3600
    )

    path, token = await _continue(in_8_days)

    assert path == "/kbs/1"
    account = await sessions.resolve(token or "")
    assert account is not None
    assert (account.id != stale.id, account.has_google, account.email_verified) == (True, True, True)


async def test_a_new_google_account_with_an_invited_email_joins(
    service: GoogleAuthService,
    sessions: SessionService,
    uow: UnitOfWork,
    fake_mailer: FakeMailer,
    make_account: MakeAccount,
    make_organization: MakeOrganization,
) -> None:
    bruno = await make_account(email="bruno@example.com", name="Bruno")
    team = await make_organization(bruno.id)
    invite = InviteCreate(emails=["ana@example.com"], role="member")
    await InviteService(uow, fake_mailer, AccessService(uow)).invite_to_organization(bruno.id, team.id, invite)

    _, token = await _continue(service)

    ana = await sessions.resolve(token or "")
    assert ana is not None
    assert await AccessService(uow).org_role(ana.id, team.id) == "member"
