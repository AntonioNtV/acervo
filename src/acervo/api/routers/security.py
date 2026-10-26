from typing import Annotated, Any

from fastapi import APIRouter, Depends

from acervo.api.deps import SIGNED_IN, CurrentAccount, get_security_log, get_settings
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.security import SecurityEventRead, SecurityOptions
from acervo.services.security_log import SecurityLog

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1/security", tags=["security"], dependencies=SIGNED_IN, responses={401: ERROR, 422: ERROR})


@router.get("/activity", response_model=list[SecurityEventRead])
async def activity(
    account: CurrentAccount, log: Annotated[SecurityLog, Depends(get_security_log)]
) -> list[SecurityEventRead]:
    """Conta › Atividade: the account's last 90 days, newest first."""
    return await log.activity(account.id)


@router.get("/options", response_model=SecurityOptions)
async def options(settings: Annotated[Settings, Depends(get_settings)]) -> SecurityOptions:
    """What Conta › Segurança and "2FA exigido" may offer."""
    return SecurityOptions(whatsapp_enabled=settings.whatsapp_enabled)
