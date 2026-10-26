from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from acervo.api.deps import current_account, get_base_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.kb import KbCreate, KbEdit, KbRead, KbSummary
from acervo.schemas.organization import BaseAccess, BaseMemberChange, GeneralAccess
from acervo.services.base_service import BaseService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/kbs",
    tags=["kbs"],
    dependencies=[Depends(current_account)],
    responses={401: ERROR, 403: ERROR, 422: ERROR},
)

Service = Annotated[BaseService, Depends(get_base_service)]


class GeneralAccessChange(BaseModel):
    """What every member of the base's organization gets on it."""

    general_access: GeneralAccess = Field(description="Leitor or Editor for everyone; none for only the people added.")


@router.get("", response_model=list[KbSummary])
async def list_kbs(service: Service, q: str = "", organization_id: UUID | None = None) -> list[KbSummary]:
    """Live bases of the organization (the Pessoal when none) the person can see, most recently edited first; the
    Pessoal also lists the bases shared with the person as a guest, with `shared_by`. `q` filters by name, ignoring
    case and accents."""
    return await service.list(q, organization_id)


@router.post("", status_code=201, response_model=KbRead)
async def create_kb(body: KbCreate, service: Service) -> KbRead:
    return await service.create(body)


@router.get("/{kb_id}", response_model=KbRead, responses={404: ERROR})
async def get_kb(kb_id: UUID, service: Service) -> KbRead:
    """A live base the person can see, with `organization_id`, `my_role` and `shared_by`; 404 for any other, so a
    base's name never reaches whoever cannot open it."""
    return await service.get(kb_id)


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


@router.get("/{kb_id}/access", response_model=BaseAccess, responses={404: ERROR})
async def get_access(kb_id: UUID, service: Service) -> BaseAccess:
    """Who reaches the base: the general access and the people added to it."""
    return await service.access(kb_id)


@router.put("/{kb_id}/access", response_model=BaseAccess, responses={404: ERROR})
async def set_general_access(kb_id: UUID, body: GeneralAccessChange, service: Service) -> BaseAccess:
    """Base Admin only; a Pessoal base has no general access (422)."""
    return await service.set_general_access(kb_id, body.general_access)


@router.put("/{kb_id}/members/{account_id}", response_model=BaseAccess, responses={404: ERROR})
async def put_member(kb_id: UUID, account_id: UUID, body: BaseMemberChange, service: Service) -> BaseAccess:
    """Base Admin only: changes the role of someone added to the base, or adds a member of its organization; anyone
    else is invited."""
    return await service.put_member(kb_id, account_id, body.role)


@router.delete("/{kb_id}/members/{account_id}", response_model=BaseAccess, responses={404: ERROR})
async def remove_member(kb_id: UUID, account_id: UUID, service: Service) -> BaseAccess:
    return await service.remove_member(kb_id, account_id)
