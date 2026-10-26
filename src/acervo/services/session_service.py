import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead, SessionCreate, SessionUpdate

# Sliding the expiry on every request would write on every request.
RENEW_EVERY = timedelta(minutes=1)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class SessionService:
    """Signed-in browsers: the cookie holds a random token, the table its hash."""

    def __init__(self, uow: UnitOfWork, session_days: int, now: Callable[[], datetime] = _now) -> None:
        self._uow = uow
        self._lifetime = timedelta(days=session_days)
        self._now = now

    async def create(self, account_id: UUID, user_agent: str | None) -> str:
        """Starts a session and gives the token for the cookie."""
        token = secrets.token_urlsafe(32)
        now = self._now()
        await self._uow.sessions.create(
            SessionCreate(
                token_hash=token_hash(token),
                account_id=account_id,
                last_seen_at=now,
                expires_at=now + self._lifetime,
                user_agent=user_agent,
            )
        )
        await self._uow.commit()
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
