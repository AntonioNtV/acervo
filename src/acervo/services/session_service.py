import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from acervo.core.errors import NotFoundError, ValidationError
from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, SessionCreate, SessionRecord, SessionUpdate, SignInMethod
from acervo.schemas.security import SecurityEventKind, SessionRead
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.security_log import SecurityLog

# Sliding the expiry on every request would write on every request.
RENEW_EVERY = timedelta(minutes=1)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class SessionService:
    """Signed-in browsers: the cookie holds a random token, the table its hash."""

    def __init__(
        self,
        uow: UnitOfWork,
        session_days: int,
        now: Callable[[], datetime] = _now,
        mailer: Mailer | None = None,
    ) -> None:
        # Without a mailer (sessions a test makes directly) no `new_sign_in` goes out.
        self._uow = uow
        self._lifetime = timedelta(days=session_days)
        self._now = now
        self._mailer = mailer

    async def create(self, account_id: UUID, user_agent: str | None, method: SignInMethod = "password") -> str:
        """Starts a session, logs the sign-in and gives the token for the cookie. A browser the account never signed
        in from (by browser and system, not by version) gets `new_sign_in` by email; the first sign-in of an account
        does not."""
        token = secrets.token_urlsafe(32)
        now = self._now()
        devices = {device(agent) for agent in await self._uow.security_events.sign_in_agents(account_id)}
        await SecurityLog(self._uow).record(
            SecurityEventKind.SIGNED_IN, account_id=account_id, data={"method": method}, user_agent=user_agent
        )
        await self._uow.sessions.create(
            SessionCreate(
                token_hash=token_hash(token),
                account_id=account_id,
                last_seen_at=now,
                expires_at=now + self._lifetime,
                user_agent=user_agent,
                method=method,
            )
        )
        await self._uow.commit()
        browser, system = device(user_agent)
        if self._mailer is not None and devices and (browser, system) not in devices:
            account = await self._uow.accounts.get(account_id)
            values = {
                "name": account.name,
                "browser": browser or "",
                "system": system or "",
                "method": method,
                "link": "/conta/sessoes",
            }
            await self._mailer.send(account.email, MailTemplate.NEW_SIGN_IN, account.language, values)
        return token

    async def resolve(self, token: str) -> AccountRead | None:
        """The account of a live session, which lasts `session_days` from its last request; None otherwise."""
        session = await self._uow.sessions.get_by(token_hash=token_hash(token))
        now = self._now()
        if session is None or session.expires_at <= now:
            return None
        if now - session.last_seen_at >= RENEW_EVERY:
            renewal = SessionUpdate(last_seen_at=now, expires_at=now + self._lifetime)
            await self._uow.sessions.update(session.id, renewal)
            await self._uow.commit()
        return AccountRead.of(await self._uow.accounts.get(session.account_id))

    async def end(self, token: str) -> None:
        await self._uow.sessions.delete_by_token(token_hash(token))
        await self._uow.commit()

    async def end_all(self, account_id: UUID, except_token: str | None = None) -> None:
        """Ends every session of the account, but the one of `except_token` when given."""
        keep = None if except_token is None else token_hash(except_token)
        await self._uow.sessions.delete_of_account(account_id, keep_token_hash=keep)
        await self._uow.commit()

    async def of_account(self, account_id: UUID, current_id: UUID) -> list[SessionRead]:
        """The account's live sessions, the last used first."""
        now = self._now()
        return [
            _read(session, current_id)
            for session in await self._uow.sessions.of_account(account_id)
            if session.expires_at > now
        ]

    async def end_one(self, account_id: UUID, session_id: UUID, current_id: UUID) -> None:
        """Ends another session of the account; the current one ends by signing out."""
        if session_id == current_id:
            raise ValidationError("the current session ends by signing out", {"id": str(session_id)})
        ended = await self._uow.sessions.get_by(id=session_id)
        if ended is None or ended.account_id != account_id:
            raise NotFoundError(f"session {session_id} not found", {"id": str(session_id)})
        await self._uow.sessions.delete(session_id)
        browser, system = device(ended.user_agent)
        await self._log_ended(account_id, current_id, {"browser": browser, "system": system})

    async def end_others(self, account_id: UUID, current_id: UUID) -> None:
        current = await self._uow.sessions.get(current_id)
        await self._uow.sessions.delete_of_account(account_id, keep_token_hash=current.token_hash)
        await self._log_ended(account_id, current_id, {"others": True})

    async def _log_ended(self, account_id: UUID, current_id: UUID, data: dict[str, object]) -> None:
        current = await self._uow.sessions.get(current_id)
        await SecurityLog(self._uow).record(
            SecurityEventKind.SESSION_ENDED,
            account_id=account_id,
            actor_id=account_id,
            data=data,
            user_agent=current.user_agent,
        )
        await self._uow.commit()


def _read(session: SessionRecord, current_id: UUID) -> SessionRead:
    browser, system = device(session.user_agent)
    return SessionRead(
        id=session.id,
        browser=browser,
        system=system,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        current=session.id == current_id,
        method=session.method,
    )
