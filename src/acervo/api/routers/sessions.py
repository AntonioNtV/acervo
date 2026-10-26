from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import SIGNED_IN, CurrentAccount, current_session_id, get_account_service, get_session_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.security import Reauthenticate, SessionRead
from acervo.services.account_service import AccountService
from acervo.services.session_service import SessionService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1/sessions", tags=["sessions"], dependencies=SIGNED_IN, responses={401: ERROR, 422: ERROR})

Service = Annotated[SessionService, Depends(get_session_service)]
CurrentSession = Annotated[UUID, Depends(current_session_id)]


@router.get("", response_model=list[SessionRead])
async def list_sessions(account: CurrentAccount, current: CurrentSession, service: Service) -> list[SessionRead]:
    """Every open session of the account, the last used first."""
    return await service.of_account(account.id, current)


@router.post("/end-others", status_code=204)
async def end_other_sessions(account: CurrentAccount, current: CurrentSession, service: Service) -> None:
    """Sair de todas as outras: every session but this one ends."""
    await service.end_others(account.id, current)


@router.delete("/{session_id}", status_code=204, responses={404: ERROR})
async def end_session(session_id: UUID, account: CurrentAccount, current: CurrentSession, service: Service) -> None:
    """Ends another session of the account; the current one is 422 (it ends by signing out)."""
    await service.end_one(account.id, session_id, current)


@router.post("/reauthenticate", status_code=204, responses={429: ERROR})
async def reauthenticate(
    body: Reauthenticate,
    account: CurrentAccount,
    current: CurrentSession,
    service: Annotated[AccountService, Depends(get_account_service)],
) -> None:
    """The password again lets this session make sensitive changes for 10 minutes.

    A wrong password is 401 `invalid_credentials` and counts toward the sign-in lockout (429).
    """
    await service.reauthenticate(account.id, current, body.password)
