from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Header, Response

from acervo.api.cookies import (
    PENDING_COOKIE,
    SESSION_COOKIE,
    clear_pending_cookie,
    clear_session_cookie,
    set_pending_cookie,
    set_session_cookie,
)
from acervo.api.deps import CurrentAccount, get_auth_service, get_settings
from acervo.core.settings import Settings
from acervo.schemas.account import AccountRead, EmailCodeIn, ResetConfirm, ResetRequest, SignIn, SignUp
from acervo.schemas.common import ErrorResponse
from acervo.schemas.security import PendingSignIn, TwoFactorConfirm, TwoFactorResend
from acervo.services.auth_service import CODE_TTL, AuthService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1/auth", tags=["auth"], responses={422: ERROR})

Service = Annotated[AuthService, Depends(get_auth_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]
UserAgent = Annotated[str | None, Header()]
PendingToken = Annotated[str | None, Cookie(alias=PENDING_COOKIE)]


@router.post("/sign-up", status_code=201, response_model=AccountRead, responses={409: ERROR})
async def sign_up(body: SignUp, service: Service) -> AccountRead:
    """An unconfirmed account; a 6-digit code goes to the email."""
    return await service.sign_up(body)


@router.post("/verify-email", response_model=AccountRead)
async def verify_email(
    body: EmailCodeIn, response: Response, service: Service, settings: AppSettings, user_agent: UserAgent = None
) -> AccountRead:
    """Confirms the email with its code and signs in."""
    account, token = await service.verify_email(body, user_agent)
    set_session_cookie(response, token, settings)
    return account


@router.post("/resend-code", status_code=204, responses={429: ERROR})
async def resend_code(body: ResetRequest, service: Service) -> None:
    """A new code, the old one no longer valid; 204 also when the email has no account."""
    await service.resend_code(body.email)


@router.post("/sign-in", response_model=AccountRead | PendingSignIn, responses={401: ERROR, 429: ERROR})
async def sign_in(
    body: SignIn, response: Response, service: Service, settings: AppSettings, user_agent: UserAgent = None
) -> AccountRead | PendingSignIn:
    """Signs in; with two-step verification on, sends the code and answers `PendingSignIn` instead, with a pending
    cookie for `POST /v1/auth/two-factor`."""
    signed, token = await service.sign_in(body, user_agent)
    if isinstance(signed, PendingSignIn):
        set_pending_cookie(response, token, int(CODE_TTL.total_seconds()), settings)
    else:
        set_session_cookie(response, token, settings)
    return signed


@router.post("/two-factor", response_model=AccountRead, responses={429: ERROR})
async def finish_two_factor(
    body: TwoFactorConfirm,
    response: Response,
    service: Service,
    settings: AppSettings,
    token: PendingToken = None,
    user_agent: UserAgent = None,
) -> AccountRead:
    """The code of the pending sign-in signs in; `code_invalid` once wrong, expired or out of tries."""
    account, session = await service.finish_two_factor(token, body.code, user_agent)
    clear_pending_cookie(response, settings)
    set_session_cookie(response, session, settings)
    return account


@router.post("/two-factor/resend", response_model=PendingSignIn, responses={429: ERROR})
async def resend_two_factor(body: TwoFactorResend, service: Service, token: PendingToken = None) -> PendingSignIn:
    """A new code for the pending sign-in, at most once a minute; `channel: email` sends it by email."""
    return await service.resend_two_factor(token, body.channel == "email")


@router.post("/sign-out", status_code=204)
async def sign_out(
    response: Response,
    service: Service,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    if token is not None:
        await service.sign_out(token)
    clear_session_cookie(response, settings)


@router.get("/me", response_model=AccountRead, responses={401: ERROR})
async def me(account: CurrentAccount) -> AccountRead:
    return account


@router.post("/unsubscribe/{token}", status_code=204, responses={404: ERROR})
async def unsubscribe(token: str, service: Service, settings: AppSettings) -> None:
    """Parar de receber: turns off the toggle the emailed link carries, without signing in; any body, so the
    RFC 8058 one-click POST works too. 404 `not_found` for a bad link or a deleted account."""
    await service.set_notification(settings.session_secret.get_secret_value(), token, False)


@router.post("/resubscribe/{token}", status_code=204, responses={404: ERROR})
async def resubscribe(token: str, service: Service, settings: AppSettings) -> None:
    """Turns the toggle of the same link back on."""
    await service.set_notification(settings.session_secret.get_secret_value(), token, True)


@router.post("/reset", status_code=204)
async def request_reset(body: ResetRequest, service: Service) -> None:
    """A single-use link valid for an hour goes to the email; 204 also when the email has no account."""
    await service.request_reset(body.email)


@router.post("/reset/confirm", response_model=AccountRead)
async def confirm_reset(
    body: ResetConfirm, response: Response, service: Service, settings: AppSettings, user_agent: UserAgent = None
) -> AccountRead:
    """Sets the password, ends every session of the account and signs in."""
    account, token = await service.confirm_reset(body, user_agent)
    set_session_cookie(response, token, settings)
    return account
