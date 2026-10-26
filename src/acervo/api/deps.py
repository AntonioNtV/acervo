import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Query, Request, Response

from acervo.api.cookies import SESSION_COOKIE, set_session_cookie
from acervo.core import signing
from acervo.core.errors import AuthError, ReauthenticationRequired
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
from acervo.schemas.organization import BaseRole
from acervo.services.access_service import AccessService
from acervo.services.account_service import AccountService
from acervo.services.attachment_service import AttachmentService
from acervo.services.auth_service import AuthService
from acervo.services.base_service import BaseService
from acervo.services.cover_service import CoverService
from acervo.services.duplicate_service import DuplicateService
from acervo.services.export_service import ExportService
from acervo.services.favorite_service import FavoriteService
from acervo.services.file_service import FileService
from acervo.services.google_auth_service import GoogleAuthService
from acervo.services.google_client import GoogleClient
from acervo.services.invite_service import InviteService
from acervo.services.link_preview_service import LinkPreviewService
from acervo.services.mailer import Mailer
from acervo.services.organization_service import OrganizationService
from acervo.services.page_service import PageService
from acervo.services.passkey_service import PasskeyService
from acervo.services.security_log import SecurityLog
from acervo.services.session_service import SessionService, token_hash
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService
from acervo.services.two_factor_service import TwoFactorService
from acervo.services.whatsapp import WhatsAppSender

# How long a sign-in, or asking the password or a passkey again, lets the session make sensitive changes.
RECENT_SIGN_IN = timedelta(minutes=10)


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


def get_whatsapp(request: Request) -> WhatsAppSender:
    whatsapp: WhatsAppSender = request.app.state.whatsapp
    return whatsapp


async def get_uow(request: Request) -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork(request.app.state.session_factory) as uow:
        yield uow


def get_base_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> BaseService:
    return BaseService(uow)


def get_tree_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> TreeService:
    return TreeService(uow)


def get_page_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> PageService:
    return PageService(uow)


def get_file_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)], storage: Annotated[Storage, Depends(get_storage)]
) -> FileService:
    return FileService(uow, storage)


def get_favorite_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> FavoriteService:
    return FavoriteService(uow)


def get_duplicate_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> DuplicateService:
    return DuplicateService(uow)


def get_cover_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CoverService:
    return CoverService(uow, storage, settings.cover_max_bytes)


def get_export_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)], storage: Annotated[Storage, Depends(get_storage)]
) -> ExportService:
    return ExportService(uow, storage)


def get_attachment_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AttachmentService:
    return AttachmentService(uow, storage, settings.attachment_max_bytes)


def get_link_preview_service(settings: Annotated[Settings, Depends(get_settings)]) -> LinkPreviewService:
    return LinkPreviewService(settings.link_preview_timeout_seconds, settings.link_preview_max_bytes)


def get_session_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionService:
    return SessionService(uow, settings.session_days, mailer=mailer)


def get_auth_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    whatsapp: Annotated[WhatsAppSender, Depends(get_whatsapp)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(uow, sessions, mailer, whatsapp, settings.whatsapp_language)


def get_two_factor_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    whatsapp: Annotated[WhatsAppSender, Depends(get_whatsapp)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TwoFactorService:
    return TwoFactorService(uow, mailer, whatsapp, settings.whatsapp_language)


def get_account_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccountService:
    return AccountService(uow, storage, mailer, settings.photo_max_bytes)


def get_google_client(settings: Annotated[Settings, Depends(get_settings)]) -> GoogleClient:
    secret = settings.google_client_secret
    return GoogleClient(settings.google_client_id or "", secret.get_secret_value() if secret else "")


def get_google_auth_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    google: Annotated[GoogleClient, Depends(get_google_client)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GoogleAuthService:
    # Through the web app's origin (its /v1 proxy), so the session cookie lands where the app reads it.
    redirect_uri = f"{settings.public_url.rstrip('/')}/v1/auth/google/callback"
    secret = settings.session_secret.get_secret_value()
    return GoogleAuthService(uow, sessions, google, mailer, secret, redirect_uri)


def get_passkey_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PasskeyService:
    secret = settings.session_secret.get_secret_value()
    return PasskeyService(uow, mailer, secret, settings.webauthn_rp_id, settings.webauthn_origin, sessions)


def get_security_log(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> SecurityLog:
    return SecurityLog(uow)


def get_access_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> AccessService:
    return AccessService(uow)


def get_organization_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    access: Annotated[AccessService, Depends(get_access_service)],
) -> OrganizationService:
    return OrganizationService(uow, storage, mailer, access)


def get_invite_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
    access: Annotated[AccessService, Depends(get_access_service)],
) -> InviteService:
    return InviteService(uow, mailer, access)


async def current_account(
    response: Response,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AccountRead:
    """The account of the session cookie; 401 when there is none or it ended."""
    account = None if token is None else await sessions.resolve(token)
    if token is None or account is None:
        raise AuthError("Missing or ended session.")
    # What the repositories answer for this account (a node's `favorite`) reads it from the request's session.
    uow.act_as(account.id)
    # The session slides with each request, so the cookie's Max-Age slides with it.
    set_session_cookie(response, token, settings)
    return account


CurrentAccount = Annotated[AccountRead, Depends(current_account)]

SIGNED_IN = [Depends(current_account)]


async def current_session_id(
    _: CurrentAccount,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UUID:
    """The session of the request, which the links it mints are bound to."""
    session = await uow.sessions.get_by(token_hash=token_hash(token or ""))
    if session is None:
        raise AuthError("Missing or ended session.")
    return session.id


async def signed_in_recently(
    session_id: Annotated[UUID, Depends(current_session_id)], uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> bool:
    """Whether the session of the request signed in or reauthenticated within `RECENT_SIGN_IN`."""
    session = await uow.sessions.get(session_id)
    return datetime.now(UTC) - (session.reauthenticated_at or session.created_at) <= RECENT_SIGN_IN


async def recent_sign_in(
    session_id: Annotated[UUID, Depends(current_session_id)],
    recent: Annotated[bool, Depends(signed_in_recently)],
) -> UUID:
    """The session of the request, signed in or reauthenticated within `RECENT_SIGN_IN`; 403
    `reauthentication_required` otherwise."""
    if not recent:
        raise ReauthenticationRequired("Confirm the password or a passkey to make this change.")
    return session_id


RecentSignIn = Annotated[UUID, Depends(recent_sign_in)]
SignedInRecently = Annotated[bool, Depends(signed_in_recently)]


def session_or_signature(purpose: signing.Purpose) -> Callable[..., Awaitable[None]]:
    """A session, or a link signed in a still live session for `purpose` of exactly this content of the node and
    not yet expired."""

    async def dependency(
        node_id: UUID,
        response: Response,
        uow: Annotated[UnitOfWork, Depends(get_uow)],
        sessions: Annotated[SessionService, Depends(get_session_service)],
        settings: Annotated[Settings, Depends(get_settings)],
        # Out of the schema: only the file route takes a version, and it declares the parameter itself.
        version_id: Annotated[UUID | None, Query(include_in_schema=False)] = None,
        session: UUID | None = None,
        expires: int | None = None,
        signature: str | None = None,
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> None:
        secret = settings.session_secret.get_secret_value()
        if (
            session is not None
            and expires is not None
            and signature is not None
            and signing.verify(secret, purpose, node_id, version_id, session, expires, signature, time.time())
        ):
            live = await uow.sessions.get_by(id=session)
            if live is not None and live.expires_at > datetime.now(UTC):
                # The link acts for whoever minted it, so the base's roles are checked as they are now.
                uow.act_as(live.account_id)
                return
        await current_account(response, uow, sessions, settings, token)

    return dependency


async def _require_base(uow: UnitOfWork, access: AccessService, kb_id: UUID, at_least: BaseRole) -> None:
    # Set by the session or signature dependency that runs before this one.
    if uow.account_id is None:
        raise AuthError("Missing or ended session.")
    await access.require_base(uow.account_id, kb_id, at_least)


def in_base(at_least: BaseRole) -> Callable[..., Awaitable[None]]:
    """The asking account has at least `at_least` in base `kb_id`; 403 `forbidden` otherwise."""

    async def dependency(
        kb_id: UUID,
        uow: Annotated[UnitOfWork, Depends(get_uow)],
        access: Annotated[AccessService, Depends(get_access_service)],
    ) -> None:
        await _require_base(uow, access, kb_id, at_least)

    return dependency


def on_node(at_least: BaseRole) -> Callable[..., Awaitable[None]]:
    """The asking account has at least `at_least` in the base of node `node_id`, live or trashed; 403 `forbidden`
    otherwise."""

    async def dependency(
        node_id: UUID,
        uow: Annotated[UnitOfWork, Depends(get_uow)],
        access: Annotated[AccessService, Depends(get_access_service)],
    ) -> None:
        await _require_base(uow, access, (await uow.nodes.get(node_id)).kb_id, at_least)

    return dependency
