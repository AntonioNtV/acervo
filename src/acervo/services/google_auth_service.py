import asyncio
import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from acervo.core import signing
from acervo.core.errors import AcervoError, CodeInvalid, InvalidCredentials, LastWayIn
from acervo.core.passwords import verify_password
from acervo.domain.user_agent import device
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountCreate, AccountRead, AccountRecord, AccountUpdate
from acervo.schemas.security import SecurityEventKind
from acervo.services.access_service import AccessService
from acervo.services.auth_service import UNVERIFIED_KEPT
from acervo.services.google_client import GoogleClient, GoogleIdentity
from acervo.services.invite_service import InviteService
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.security_log import SecurityLog
from acervo.services.session_service import SessionService

STATE_SECONDS = 10 * 60
LINK_SECONDS = 10 * 60
FAILED = "/entrar?erro=google"


@dataclass(frozen=True)
class Landing:
    """Where the web app opens after Google, and the session to start when someone signed in."""

    path: str
    session_token: str | None = None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _same_origin_path(next: str | None) -> str:
    # `//host` and `/\host` are other hosts to a browser, which also drops tabs and newlines before reading a URL.
    if next and next.startswith("/") and not next.startswith("//") and "\\" not in next and next.isprintable():
        return next
    return "/"


class GoogleAuthService:
    """Sign in and sign up with Google, linking to the account that already has the email."""

    def __init__(
        self,
        uow: UnitOfWork,
        sessions: SessionService,
        google: GoogleClient,
        mailer: Mailer,
        secret: str,
        redirect_uri: str,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._uow = uow
        self._sessions = sessions
        self._google = google
        self._mailer = mailer
        self._secret = secret
        self._redirect_uri = redirect_uri
        self._now = now

    def start(self, next: str | None) -> tuple[str, str]:
        """Google's URL to send the browser to, and the value of the short-lived cookie the callback checks."""
        state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        challenge = _b64(hashlib.sha256(verifier.encode()).digest())
        cookie = self._seal("google_state", STATE_SECONDS, state=state, verifier=verifier, next=_same_origin_path(next))
        return self._google.authorize_url(state, challenge, self._redirect_uri), cookie

    async def finish(self, code: str | None, state: str | None, cookie: str | None, user_agent: str | None) -> Landing:
        """Signs in or up the person Google confirmed, or sends them to confirm the password of the account to
        link; any failure lands on Entrar with the Google error."""
        started = self._unseal("google_state", cookie)
        if (
            code is None
            or state is None
            or started is None
            or not hmac.compare_digest(state.encode(), started["state"].encode())
        ):
            return Landing(FAILED)
        try:
            person = await self._google.identity(code, started["verifier"], self._redirect_uri)
            return await self._land(person, started["next"], user_agent)
        except AcervoError:
            return Landing(FAILED)

    async def link(self, token: str, password: str, user_agent: str | None) -> tuple[AccountRead, str]:
        """Links Google to the account of a link token once its password is right, and signs it in."""
        pending = self._unseal("google_link", token)
        if pending is None:
            raise CodeInvalid("The link expired or is not valid.")
        account = await self._uow.accounts.get(UUID(pending["account"]))
        if account.google_sub is not None:
            raise CodeInvalid("The link expired or is not valid.")
        if account.password_hash is None or not await asyncio.to_thread(
            verify_password, password, account.password_hash
        ):
            raise InvalidCredentials("Wrong email or password.")
        # Google confirmed the email, so the account no longer waits for its code.
        update = AccountUpdate(google_sub=pending["sub"], email_verified_at=account.email_verified_at or self._utc())
        linked = await self._uow.accounts.update(account.id, update)
        if account.email_verified_at is None:
            await self._claim_invites(account.id)
        return AccountRead.of(linked), await self._sign_in_linked(linked, user_agent)

    async def unlink(self, account_id: UUID, session_id: UUID) -> AccountRead:
        """Unlinks Google, unless it is the only way left to sign in."""
        # Locked first, so a passkey removed at the same time cannot leave the account with no way in.
        passkeys = await self._uow.passkeys.of_account(account_id, lock=True)
        account = await self._uow.accounts.get(account_id)
        if account.google_sub is None:
            return AccountRead.of(account)
        if account.password_hash is None and not passkeys:
            raise LastWayIn("Google is the only way to sign in to this account.")
        session = await self._uow.sessions.get(session_id)
        unlinked = await self._uow.accounts.update(account_id, AccountUpdate(google_sub=None))
        await SecurityLog(self._uow).record(
            SecurityEventKind.GOOGLE_UNLINKED, account_id=account_id, actor_id=account_id, user_agent=session.user_agent
        )
        await self._uow.commit()
        await self._tell(unlinked, SecurityEventKind.GOOGLE_UNLINKED, session.user_agent)
        return AccountRead.of(unlinked)

    async def _land(self, person: GoogleIdentity, next: str, user_agent: str | None) -> Landing:
        if not person.email_verified:
            return Landing(FAILED)
        account = await self._uow.accounts.get_by(google_sub=person.sub)
        if account is None:
            await self._uow.accounts.free_if_stale(person.email, self._utc() - UNVERIFIED_KEPT)
            account = await self._uow.accounts.by_email(person.email)
            if account is not None and account.google_sub is not None:
                return Landing(FAILED)
            if account is not None and account.email_verified_at is None:
                token = self._seal("google_link", LINK_SECONDS, account=str(account.id), sub=person.sub)
                return Landing(f"/entrar/vincular?{urlencode({'token': token, 'next': next})}")
            if account is not None:
                account = await self._uow.accounts.update(account.id, AccountUpdate(google_sub=person.sub))
                return Landing(next, await self._sign_in_linked(account, user_agent))
            name = person.name or person.email.split("@")[0]
            created = AccountCreate(email=person.email, name=name, google_sub=person.sub, email_verified_at=self._utc())
            account = await self._uow.accounts.create(created)
            await self._uow.organizations.create_personal(account.id)
            await self._claim_invites(account.id)
        return Landing(next, await self._sessions.create(account.id, user_agent, "google"))

    async def _sign_in_linked(self, account: AccountRecord, user_agent: str | None) -> str:
        """Logs and emails Google just linked to the account, and signs it in; gives the session token."""
        await SecurityLog(self._uow).record(
            SecurityEventKind.GOOGLE_LINKED, account_id=account.id, actor_id=account.id, user_agent=user_agent
        )
        token = await self._sessions.create(account.id, user_agent, "google")
        await self._tell(account, SecurityEventKind.GOOGLE_LINKED, user_agent)
        return token

    async def _tell(self, account: AccountRecord, change: SecurityEventKind, user_agent: str | None) -> None:
        browser, system = device(user_agent)
        values = {
            "name": account.name,
            "change": change.value,
            "browser": browser or "",
            "system": system or "",
            "link": "/conta/seguranca",
        }
        await self._mailer.send(account.email, MailTemplate.SECURITY_CHANGE, account.language, values)

    async def _claim_invites(self, account_id: UUID) -> None:
        """An invited email that just got a confirmed account joins what it was invited to (spec §3)."""
        await InviteService(self._uow, self._mailer, AccessService(self._uow), self._utc).claim(account_id)

    def _utc(self) -> datetime:
        return datetime.fromtimestamp(self._now(), UTC)

    def _seal(self, purpose: str, seconds: int, **values: str) -> str:
        return signing.seal(self._secret, purpose, int(self._now()) + seconds, **values)

    def _unseal(self, purpose: str, sealed: str | None) -> dict[str, Any] | None:
        return signing.unseal(self._secret, purpose, sealed, self._now())
