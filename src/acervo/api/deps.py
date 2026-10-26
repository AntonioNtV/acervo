import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Query, Request, Response

from acervo.api.cookies import SESSION_COOKIE, set_session_cookie
from acervo.core import signing
from acervo.core.errors import AuthError
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRead
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
from acervo.services.link_preview_service import LinkPreviewService
from acervo.services.mailer import Mailer
from acervo.services.page_service import PageService
from acervo.services.session_service import SessionService, token_hash
from acervo.services.storage import Storage
from acervo.services.tree_service import TreeService


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


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
    uow: Annotated[UnitOfWork, Depends(get_uow)], settings: Annotated[Settings, Depends(get_settings)]
) -> SessionService:
    return SessionService(uow, settings.session_days)


def get_auth_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AuthService:
    return AuthService(uow, sessions, mailer)


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
    settings: Annotated[Settings, Depends(get_settings)],
) -> GoogleAuthService:
    # Through the web app's origin (its /v1 proxy), so the session cookie lands where the app reads it.
    redirect_uri = f"{settings.public_url.rstrip('/')}/v1/auth/google/callback"
    return GoogleAuthService(uow, sessions, google, settings.session_secret.get_secret_value(), redirect_uri)


async def current_account(
    response: Response,
    sessions: Annotated[SessionService, Depends(get_session_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AccountRead:
    """The account of the session cookie; 401 when there is none or it ended."""
    account = None if token is None else await sessions.resolve(token)
    if token is None or account is None:
        raise AuthError("Missing or ended session.")
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
                return
        await current_account(response, sessions, settings, token)

    return dependency
