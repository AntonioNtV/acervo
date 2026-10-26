from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import current_account, get_base_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.kb import KbCreate, KbEdit, KbRead, KbSummary
from acervo.services.base_service import BaseService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/kbs",
    tags=["kbs"],
    dependencies=[Depends(current_account)],
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[BaseService, Depends(get_base_service)]


@router.get("", response_model=list[KbSummary])
async def list_kbs(service: Service, q: str = "") -> list[KbSummary]:
    """Live bases, most recently edited first; `q` filters by name, ignoring case and accents."""
    return await service.list(q)


@router.post("", status_code=201, response_model=KbRead)
async def create_kb(body: KbCreate, service: Service) -> KbRead:
    return await service.create(body)


@router.patch("/{kb_id}", response_model=KbRead, responses={404: ERROR})
async def update_kb(kb_id: UUID, body: KbEdit, service: Service) -> KbRead:
    return await service.update(kb_id, body)


@router.delete("/{kb_id}", response_model=KbRead, responses={404: ERROR})
async def trash_kb(kb_id: UUID, service: Service) -> KbRead:
    """Moves the base to the trash; it comes back intact with restore."""
    return await service.trash(kb_id)


@router.post("/{kb_id}/restore", response_model=KbRead, responses={404: ERROR})
async def restore_kb(kb_id: UUID, service: Service) -> KbRead:
    return await service.restore(kb_id)
