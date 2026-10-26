from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from acervo.api.cookies import set_session_cookie
from acervo.api.deps import get_session_service, get_settings, get_uow
from acervo.core.settings import Settings
from acervo.schemas.account import AccountRead
from acervo.schemas.common import ErrorResponse
from acervo.services.google_auth_service import STATE_SECONDS, GoogleAuthService
from acervo.services.google_client import GoogleClient
from acervo.services.session_service import SessionService

ERROR: dict[str, Any] = {"model": ErrorResponse}
STATE_COOKIE = "acervo_google"
PREFIX = "/v1/auth/google"

router = APIRouter(prefix=PREFIX, tags=["auth"])

AppSettings = Annotated[Settings, Depends(get_settings)]


class GoogleLinkIn(BaseModel):
    """The password that links Google to an account whose email was not yet confirmed."""

    token: str = Field(description="From the `/entrar/vincular` link the callback redirected to.")
    password: str = Field(description="The account's password.")


def get_google_client(settings: AppSettings) -> GoogleClient:
    secret = settings.google_client_secret
    return GoogleClient(settings.google_client_id or "", secret.get_secret_value() if secret else "")


def get_google_auth_service(
    # shortcut: Any, as only deps.py may import UnitOfWork; move this getter there once card 05 frees deps.py.
    uow: Annotated[Any, Depends(get_uow)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
    google: Annotated[GoogleClient, Depends(get_google_client)],
    settings: AppSettings,
) -> GoogleAuthService:
    # Through the web app's origin (its /v1 proxy), so the session cookie lands where the app reads it.
    redirect_uri = f"{settings.public_url.rstrip('/')}{PREFIX}/callback"
    return GoogleAuthService(uow, sessions, google, settings.session_secret.get_secret_value(), redirect_uri)


Service = Annotated[GoogleAuthService, Depends(get_google_auth_service)]


@router.get("/start", response_class=RedirectResponse, status_code=302)
async def google_start(service: Service, settings: AppSettings, next: str | None = None) -> RedirectResponse:
    """Sends the browser to Google; after it, the web app opens `next` when it is a path of its own, else `/`."""
    url, state = service.start(next)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_SECONDS,
        path=PREFIX,
        httponly=True,
        samesite="lax",
        secure=settings.public_url.startswith("https://"),
    )
    return response


@router.get("/callback", response_class=RedirectResponse, status_code=302)
async def google_callback(
    request: Request,
    service: Service,
    settings: AppSettings,
    code: str | None = None,
    state: str | None = None,
    started: Annotated[str | None, Cookie(alias=STATE_COOKIE)] = None,
) -> RedirectResponse:
    """Where Google returns. Signs in or up and opens `next`; opens `/entrar/vincular?token=` when the account with
    that email must confirm its password first; any failure opens `/entrar?erro=google`."""
    landing = await service.finish(code, state, started, request.headers.get("user-agent"))
    response = RedirectResponse(f"{settings.public_url.rstrip('/')}{landing.path}", status_code=302)
    # Once used, the state is gone from the browser, so the same callback cannot sign in twice.
    response.delete_cookie(STATE_COOKIE, path=PREFIX)
    if landing.session_token is not None:
        set_session_cookie(response, landing.session_token, settings)
    return response


@router.post("/link", response_model=AccountRead, responses={401: ERROR, 404: ERROR, 422: ERROR})
async def google_link(
    body: GoogleLinkIn, request: Request, response: Response, service: Service, settings: AppSettings
) -> AccountRead:
    """Links Google to the account of `token` (10 minutes) after its password, and signs in.

    A wrong password is 401 `invalid_credentials`; an expired or already linked token is 422 `code_invalid`.
    """
    account, token = await service.link(body.token, body.password, request.headers.get("user-agent"))
    set_session_cookie(response, token, settings)
    return account
