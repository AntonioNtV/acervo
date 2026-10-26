import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

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
    PasswordResetUpdate,
    ResetConfirm,
    SignIn,
    SignUp,
)
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


class AuthService:
    """Accounts by email and password: sign up, confirm the email, sign in and out, reset the password."""

    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionService,
        mailer: Mailer,
        public_url: str,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._uow = uow
        self._sessions = sessions
        self._mailer = mailer
        self._public_url = public_url
        self._now = now

    async def sign_up(self, data: SignUp) -> AccountRead:
        """An unconfirmed account and a code to its email; the email of one left unconfirmed for 7 days is free."""
        now = self._now()
        existing = await self._uow.accounts.by_email(data.email)
        if existing is not None:
            if existing.email_verified_at is not None or now - existing.created_at < UNVERIFIED_KEPT:
                raise EmailTaken("email already has an account")
            await self._uow.accounts.delete(existing.id)
        try:
            account = await self._uow.accounts.create(
                AccountCreate(email=data.email, name=data.name.strip(), password_hash=hash_password(data.password)),
                created_at=now,
            )
        except ConflictError as exc:
            raise EmailTaken("email already has an account") from exc
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
        if await self._uow.login_failures.count_since(email_lower, now - LOCKOUT_WINDOW) >= LOCKOUT_FAILURES:
            raise TooManyAttempts("too many wrong passwords for this email")
        account = await self._uow.accounts.by_email(data.email)
        password_hash = _NO_ACCOUNT_HASH if account is None else account.password_hash or _NO_ACCOUNT_HASH
        if not verify_password(data.password, password_hash) or account is None or account.password_hash is None:
            await self._uow.login_failures.create(LoginFailureCreate(email_lower=email_lower), created_at=now)
            await self._uow.commit()
            raise InvalidCredentials("wrong email or password")
        if needs_rehash(account.password_hash):
            await self._uow.accounts.update(account.id, AccountUpdate(password_hash=hash_password(data.password)))
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
        account = await self._uow.accounts.by_email(email)
        if account is None:
            return
        token = secrets.token_urlsafe(32)
        reset = PasswordResetCreate(
            token_hash=token_hash(token), account_id=account.id, expires_at=self._now() + RESET_TTL
        )
        await self._uow.password_resets.create(reset)
        await self._uow.commit()
        values = {"link": f"{self._public_url}/redefinir-senha/{token}", "name": account.name}
        await self._mailer.send(account.email, MailTemplate.RESET_LINK, account.language, values)

    async def confirm_reset(self, data: ResetConfirm, user_agent: str | None) -> tuple[AccountRead, str]:
        """Sets the password, ends every session of the account and starts a new one; gives the account and token."""
        now = self._now()
        reset = await self._uow.password_resets.get_by(token_hash=token_hash(data.token))
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise CodeInvalid("wrong, expired or used link")
        await self._uow.password_resets.update(reset.id, PasswordResetUpdate(used_at=now))
        account = await self._uow.accounts.get(reset.account_id)
        # The link reached the inbox, which confirms the email.
        change = AccountUpdate(password_hash=hash_password(data.password))
        if account.email_verified_at is None:
            change.email_verified_at = now
        account = await self._uow.accounts.update(account.id, change)
        await self._sessions.end_all(account.id)
        return AccountRead.of(account), await self._sessions.create(account.id, user_agent)

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
