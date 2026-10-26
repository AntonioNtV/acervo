from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header

from acervo.api.deps import SIGNED_IN, CurrentAccount, RecentSignIn, get_two_factor_service
from acervo.schemas.account import AccountRead
from acervo.schemas.common import ErrorResponse
from acervo.schemas.security import TwoFactorConfirm, TwoFactorStart
from acervo.services.two_factor_service import TwoFactorService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/two-factor", tags=["two-factor"], dependencies=SIGNED_IN, responses={401: ERROR, 422: ERROR}
)

Service = Annotated[TwoFactorService, Depends(get_two_factor_service)]
UserAgent = Annotated[str | None, Header()]


@router.post("", response_model=AccountRead, responses={429: ERROR})
async def start_two_factor(
    body: TwoFactorStart, account: CurrentAccount, service: Service, user_agent: UserAgent = None
) -> AccountRead:
    """Email turns on at once; WhatsApp sends a code to `phone`, and turns on at `POST /v1/two-factor/confirm`."""
    return await service.start(account.id, body, user_agent)


@router.post("/confirm", response_model=AccountRead)
async def confirm_two_factor(
    body: TwoFactorConfirm, account: CurrentAccount, service: Service, user_agent: UserAgent = None
) -> AccountRead:
    """The WhatsApp code confirms the number and turns WhatsApp on in place of email."""
    return await service.confirm(account.id, body.code, user_agent)


@router.delete("", response_model=AccountRead, responses={403: ERROR})
async def disable_two_factor(
    account: CurrentAccount, _: RecentSignIn, service: Service, user_agent: UserAgent = None
) -> AccountRead:
    """Turns two-step verification off; needs a recent sign-in."""
    return await service.disable(account.id, user_agent)
