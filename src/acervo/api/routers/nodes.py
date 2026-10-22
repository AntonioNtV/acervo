from typing import Any

from fastapi import APIRouter, Depends

from acervo.api.deps import require_api_key
from acervo.schemas.common import ErrorResponse

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/nodes",
    tags=["nodes"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)
