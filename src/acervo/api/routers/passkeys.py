from typing import Any

from fastapi import APIRouter

from acervo.api.deps import SIGNED_IN
from acervo.schemas.common import ErrorResponse

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1/passkeys", tags=["passkeys"], dependencies=SIGNED_IN, responses={401: ERROR, 422: ERROR})
