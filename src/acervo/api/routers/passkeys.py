from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from acervo.api.cookies import SESSION_COOKIE, set_session_cookie
from acervo.api.deps import CurrentAccount, RecentSignIn, get_passkey_service, get_settings
from acervo.core.settings import Settings
from acervo.schemas.account import AccountRead
from acervo.schemas.common import ErrorResponse
from acervo.schemas.security import PasskeyRead, PasskeyRename, WebAuthnCredential, WebAuthnOptions
from acervo.services.passkey_service import CHALLENGE_SECONDS, PasskeyService

ERROR: dict[str, Any] = {"model": ErrorResponse}
PREFIX = "/v1/passkeys"
CHALLENGE_COOKIE = "acervo_passkey"

# No router-wide session: the sign-in routes answer without one.
router = APIRouter(prefix=PREFIX, tags=["passkeys"], responses={401: ERROR, 422: ERROR})

AppSettings = Annotated[Settings, Depends(get_settings)]
Challenge = Annotated[str | None, Cookie(alias=CHALLENGE_COOKIE)]
Service = Annotated[PasskeyService, Depends(get_passkey_service)]


def _set_challenge(response: Response, value: str, settings: Settings) -> None:
    response.set_cookie(
        CHALLENGE_COOKIE,
        value,
        max_age=CHALLENGE_SECONDS,
        path=PREFIX,
        httponly=True,
        samesite="strict",
        secure=settings.public_url.startswith("https://"),
    )


@router.post("/register/options", response_model=WebAuthnOptions)
async def registration_options(
    account: CurrentAccount, response: Response, service: Service, settings: AppSettings
) -> WebAuthnOptions:
    """Creation options for `navigator.credentials.create()`; the challenge rides a 5-minute cookie."""
    options, challenge = await service.registration_options(account)
    _set_challenge(response, challenge, settings)
    return WebAuthnOptions(options=options)


@router.post("/register", response_model=PasskeyRead, status_code=status.HTTP_201_CREATED)
async def register(
    account: CurrentAccount,
    body: WebAuthnCredential,
    request: Request,
    response: Response,
    service: Service,
    challenge: Challenge = None,
) -> PasskeyRead:
    """Adds the passkey the browser created. An expired prompt or a credential that does not verify is 422
    `code_invalid`."""
    response.delete_cookie(CHALLENGE_COOKIE, path=PREFIX)
    return await service.register(account, body.credential, body.name, challenge, request.headers.get("user-agent"))


@router.get("", response_model=list[PasskeyRead])
async def list_passkeys(account: CurrentAccount, service: Service) -> list[PasskeyRead]:
    """The account's passkeys, oldest first."""
    return await service.of_account(account.id)


@router.patch("/{passkey_id}", response_model=PasskeyRead, responses={404: ERROR})
async def rename_passkey(
    passkey_id: UUID, body: PasskeyRename, account: CurrentAccount, service: Service
) -> PasskeyRead:
    return await service.rename(account.id, passkey_id, body.name)


@router.delete("/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT, responses={403: ERROR, 404: ERROR, 409: ERROR})
async def remove_passkey(
    passkey_id: UUID, account: CurrentAccount, _: RecentSignIn, request: Request, service: Service
) -> None:
    """Removes a passkey. Without a recent sign-in it is 403 `reauthentication_required`; the only way in of an
    account with no password and no Google is 409 `last_way_in`."""
    await service.remove(account, passkey_id, request.headers.get("user-agent"))


@router.post("/sign-in/options", response_model=WebAuthnOptions)
async def sign_in_options(response: Response, service: Service, settings: AppSettings) -> WebAuthnOptions:
    """Request options for `navigator.credentials.get()`, with no allowed credentials so the browser offers any
    passkey of the site (also as autofill); the challenge rides a 5-minute cookie."""
    options, challenge = service.sign_in_options()
    _set_challenge(response, challenge, settings)
    return WebAuthnOptions(options=options)


@router.post("/sign-in", response_model=AccountRead)
async def sign_in(
    body: WebAuthnCredential,
    request: Request,
    response: Response,
    service: Service,
    settings: AppSettings,
    challenge: Challenge = None,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AccountRead:
    """Signs in with a passkey, no second step. On a session of the same account it confirms it instead (a recent
    sign-in for sensitive changes). A passkey that does not verify is 401 `invalid_credentials`; an expired prompt
    is 422 `code_invalid`."""
    response.delete_cookie(CHALLENGE_COOKIE, path=PREFIX)
    account, session = await service.sign_in(body.credential, challenge, request.headers.get("user-agent"), token)
    set_session_cookie(response, session, settings)
    return account
