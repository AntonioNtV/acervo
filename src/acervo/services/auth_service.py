import asyncio
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from acervo.core.errors import (
    CodeInvalid,
    ConflictError,
    EmailNotVerified,
    EmailTaken,
    InvalidCredentials,
    TooManyAttempts,
)
from acervo.core.passwords import hash_password, needs_rehash, verify_password
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import (
    AccountCreate,
    AccountRead,
    AccountRecord,
    AccountUpdate,
    EmailCodeCreate,
    EmailCodeIn,
    EmailCodeUpdate,
    LoginFailureCreate,
    PasswordResetCreate,
    ResetConfirm,
    SignIn,
    SignUp,
)
from acervo.services.access_service import AccessService
from acervo.services.invite_service import InviteService
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.session_service import SessionService, token_hash

CODE_TTL = timedelta(minutes=10)
CODE_TRIES = 5
RESEND_AFTER = timedelta(seconds=60)
LOCKOUT_FAILURES = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
UNVERIFIED_KEPT = timedelta(days=7)
RESET_TTL = timedelta(hours=1)

# A wrong email is checked against this hash too, so it takes as long as a wrong password.
_NO_ACCOUNT_HASH = hash_password(secrets.token_urlsafe())


def _now() -> datetime:
    return datetime.now(UTC)


def _locked(failures: list[datetime], now: datetime) -> bool:
    """The last five failures, newest first, fell within the window: locked until a window after the newest."""
    return (
        len(failures) == LOCKOUT_FAILURES
        and failures[0] - failures[-1] <= LOCKOUT_WINDOW
        and now < failures[0] + LOCKOUT_WINDOW
    )


class AuthService:
    """Accounts by email and password: sign up, confirm the email, sign in and out, reset the password."""

    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionService,
        mailer: Mailer,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._uow = uow
        self._sessions = sessions
        self._mailer = mailer
        self._now = now

    async def sign_up(self, data: SignUp) -> AccountRead:
        """An unconfirmed account and a code to its email; the email of one left unconfirmed for 7 days is free."""
        now = self._now()
        await self._uow.accounts.free_if_stale(data.email, now - UNVERIFIED_KEPT)
        if await self._uow.accounts.by_email(data.email) is not None:
            raise EmailTaken("email already has an account")
        password_hash = await asyncio.to_thread(hash_password, data.password)
        try:
            account = await self._uow.accounts.create(
                AccountCreate(email=data.email, name=data.name.strip(), password_hash=password_hash), created_at=now
            )
        except ConflictError as exc:
            raise EmailTaken("email already has an account") from exc
        await self._uow.organizations.create_personal(account.id)
        code = await self._new_code(account)
        await self._uow.commit()
        await self._send_code(account, code)
        return AccountRead.of(account)

    async def verify_email(self, data: EmailCodeIn, user_agent: str | None) -> tuple[AccountRead, str]:
        """Confirms the email with its code and starts a session; gives the account and the session token."""
        now = self._now()
        account = await self._uow.accounts.by_email(data.email)
        live = None if account is None else await self._uow.email_codes.live(account.id, "verify_email")
        if account is None or live is None or live.expires_at <= now or live.attempts >= CODE_TRIES:
            raise CodeInvalid("wrong or expired code")
        if not hmac.compare_digest(live.code_hash, token_hash(data.code)):
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(attempts=live.attempts + 1))
            await self._uow.commit()
            raise CodeInvalid("wrong or expired code")
        await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=now))
        verified = await self._uow.accounts.update(account.id, AccountUpdate(email_verified_at=now))
        await self._claim_invites(account.id)
        return AccountRead.of(verified), await self._sessions.create(account.id, user_agent)

    async def resend_code(self, email: str) -> None:
        """A new code for an unconfirmed account, the old one no longer valid; nothing when there is none."""
        account = await self._uow.accounts.by_email(email)
        if account is None or account.email_verified_at is not None:
            return
        if await self._sent_recently(account):
            raise TooManyAttempts("a code was sent less than a minute ago")
        code = await self._new_code(account)
        await self._uow.commit()
        await self._send_code(account, code)

    async def sign_in(self, data: SignIn, user_agent: str | None) -> tuple[AccountRead, str]:
        """Starts a session; gives the account and the session token."""
        now = self._now()
        email_lower = data.email.lower()
        await self._uow.login_failures.lock(email_lower)
        if _locked(await self._uow.login_failures.latest(email_lower, LOCKOUT_FAILURES), now):
            raise TooManyAttempts("too many wrong passwords for this email")
        await self._uow.accounts.free_if_stale(data.email, now - UNVERIFIED_KEPT)
        account = await self._uow.accounts.by_email(data.email)
        password_hash = _NO_ACCOUNT_HASH if account is None else account.password_hash or _NO_ACCOUNT_HASH
        right = await asyncio.to_thread(verify_password, data.password, password_hash)
        if not right or account is None or account.password_hash is None:
            await self._uow.login_failures.create(LoginFailureCreate(email_lower=email_lower), created_at=now)
            await self._uow.login_failures.clear(email_lower, before=now - LOCKOUT_WINDOW)
            await self._uow.commit()
            raise InvalidCredentials("wrong email or password")
        if needs_rehash(account.password_hash):
            rehashed = await asyncio.to_thread(hash_password, data.password)
            await self._uow.accounts.update(account.id, AccountUpdate(password_hash=rehashed))
        if account.email_verified_at is None:
            code = None if await self._sent_recently(account) else await self._new_code(account)
            await self._uow.commit()
            if code is not None:
                await self._send_code(account, code)
            raise EmailNotVerified("email not confirmed yet")
        return AccountRead.of(account), await self._sessions.create(account.id, user_agent)

    async def sign_out(self, token: str) -> None:
        await self._sessions.end(token)

    async def request_reset(self, email: str) -> None:
        """Sends a single-use link valid for an hour, when the email has an account."""
        now = self._now()
        account = await self._uow.accounts.by_email(email)
        if account is None:
            return
        # Silent like a missing account, so the answer says nothing about the email.
        latest = await self._uow.password_resets.latest(account.id)
        if latest is not None and now - latest.created_at < RESEND_AFTER:
            return
        token = secrets.token_urlsafe(32)
        reset = PasswordResetCreate(token_hash=token_hash(token), account_id=account.id, expires_at=now + RESET_TTL)
        await self._uow.password_resets.create(reset, created_at=now)
        await self._uow.commit()
        # The template builds the URL around the token, from the app's public URL.
        values = {"link": token, "name": account.name}
        await self._mailer.send(account.email, MailTemplate.RESET_LINK, account.language, values)

    async def confirm_reset(self, data: ResetConfirm, user_agent: str | None) -> tuple[AccountRead, str]:
        """Sets the password, ends every session of the account and starts a new one; gives the account and token."""
        now = self._now()
        reset = await self._uow.password_resets.by_token(token_hash(data.token))
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise CodeInvalid("wrong, expired or used link")
        # Every link of the account dies with this one, not only the one used.
        await self._uow.password_resets.use_all(reset.account_id, now)
        account = await self._uow.accounts.get(reset.account_id)
        # The link reached the inbox, which confirms the email.
        change = AccountUpdate(password_hash=await asyncio.to_thread(hash_password, data.password))
        confirmed_now = account.email_verified_at is None
        if confirmed_now:
            change.email_verified_at = now
        account = await self._uow.accounts.update(account.id, change)
        if confirmed_now:
            await self._claim_invites(account.id)
        # Whoever set the new password through the inbox is not the one guessing it: the lock would only keep them out.
        await self._uow.login_failures.clear(account.email.lower())
        await self._sessions.end_all(account.id)
        return AccountRead.of(account), await self._sessions.create(account.id, user_agent)

    async def _claim_invites(self, account_id: UUID) -> None:
        """An invited email that just got a confirmed account joins what it was invited to (spec §3)."""
        await InviteService(self._uow, self._mailer, AccessService(self._uow), self._now).claim(account_id)

    async def _sent_recently(self, account: AccountRecord) -> bool:
        live = await self._uow.email_codes.live(account.id, "verify_email")
        return live is not None and self._now() - live.created_at < RESEND_AFTER

    async def _new_code(self, account: AccountRecord) -> str:
        """Stores a new code, the live one marked used first (one live code per account and purpose)."""
        now = self._now()
        live = await self._uow.email_codes.live(account.id, "verify_email")
        if live is not None:
            await self._uow.email_codes.update(live.id, EmailCodeUpdate(used_at=now))
        code = f"{secrets.randbelow(1_000_000):06d}"
        await self._uow.email_codes.create(
            EmailCodeCreate(
                account_id=account.id,
                purpose="verify_email",
                target_email=account.email,
                code_hash=token_hash(code),
                expires_at=now + CODE_TTL,
            ),
            created_at=now,
        )
        return code

    async def _send_code(self, account: AccountRecord, code: str) -> None:
        values = {"code": code, "name": account.name}
        await self._mailer.send(account.email, MailTemplate.VERIFY_CODE, account.language, values)
