from fastapi import APIRouter

from acervo.schemas.common import HealthResponse

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
