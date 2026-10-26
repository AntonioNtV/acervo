from typing import Any

from fastapi import APIRouter

from acervo.schemas.common import ErrorResponse

ERROR: dict[str, Any] = {"model": ErrorResponse}

# No session on the router: the Convite screen reads an invite by its token before anyone signs in.
router = APIRouter(prefix="/v1/invites", tags=["invites"], responses={422: ERROR})
