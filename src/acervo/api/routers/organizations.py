from pathlib import PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import SIGNED_IN, CurrentAccount, get_organization_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.organization import (
    MemberRead,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    RoleChange,
)
from acervo.services.organization_service import OrganizationService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/organizations",
    tags=["organizations"],
    dependencies=SIGNED_IN,
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[OrganizationService, Depends(get_organization_service)]


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(account: CurrentAccount, service: Service) -> list[OrganizationRead]:
    """The person's organizations: Pessoal first, then by name."""
    return await service.mine(account.id)


@router.post("", response_model=OrganizationRead, status_code=201)
async def create_organization(body: OrganizationCreate, account: CurrentAccount, service: Service) -> OrganizationRead:
    """The creator becomes its Owner."""
    return await service.create(account.id, body)


@router.get("/{organization_id}", response_model=OrganizationRead, responses={403: ERROR, 404: ERROR})
async def get_organization(organization_id: UUID, account: CurrentAccount, service: Service) -> OrganizationRead:
    return await service.get(account.id, organization_id)


@router.patch("/{organization_id}", response_model=OrganizationRead, responses={403: ERROR, 404: ERROR})
async def update_organization(
    organization_id: UUID, body: OrganizationUpdate, account: CurrentAccount, service: Service
) -> OrganizationRead:
    """Owners and Admins; a Pessoal keeps its name."""
    return await service.update(account.id, organization_id, body)


@router.put("/{organization_id}/logo", response_model=OrganizationRead, responses={403: ERROR, 404: ERROR})
async def set_logo(
    organization_id: UUID, file: UploadFile, account: CurrentAccount, service: Service
) -> OrganizationRead:
    """A PNG, JPEG or WebP of at most 2 MB; its centered square, 256 px, becomes the logo."""
    return await service.set_logo(account.id, organization_id, file.file)


@router.delete("/{organization_id}/logo", response_model=OrganizationRead, responses={403: ERROR, 404: ERROR})
async def remove_logo(organization_id: UUID, account: CurrentAccount, service: Service) -> OrganizationRead:
    """Back to the initials."""
    return await service.remove_logo(account.id, organization_id)


@router.get(
    "/{organization_id}/logo",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"image/png": {}}, "description": "The logo, a 256 px square."},
        403: ERROR,
        404: ERROR,
    },
)
async def organization_logo(organization_id: UUID, account: CurrentAccount, service: Service) -> StreamingResponse:
    key, body = await service.open_logo(account.id, organization_id)
    # The URL carries the logo's hash, so what one URL served never changes.
    headers = {"Cache-Control": "private, max-age=31536000, immutable", "ETag": f'"{PurePosixPath(key).stem}"'}
    return StreamingResponse(body, media_type="image/png", headers=headers)


@router.get("/{organization_id}/members", response_model=list[MemberRead], responses={403: ERROR, 404: ERROR})
async def list_members(organization_id: UUID, account: CurrentAccount, service: Service) -> list[MemberRead]:
    """Owners and Admins; a Pessoal has none (403)."""
    return await service.members(account.id, organization_id)


@router.patch(
    "/{organization_id}/members/{account_id}",
    response_model=MemberRead,
    responses={403: ERROR, 404: ERROR, 409: ERROR},
)
async def change_role(
    organization_id: UUID, account_id: UUID, body: RoleChange, account: CurrentAccount, service: Service
) -> MemberRead:
    """Owners change any role, Admins those below Owner; the last Owner stays (409 `last_owner`). The member is
    told by email."""
    return await service.change_role(account.id, organization_id, account_id, body.role)


@router.delete(
    "/{organization_id}/members/{account_id}", status_code=204, responses={403: ERROR, 404: ERROR, 409: ERROR}
)
async def remove_member(organization_id: UUID, account_id: UUID, account: CurrentAccount, service: Service) -> None:
    """Takes the member and their access to the organization's bases out; they are told by email."""
    await service.remove(account.id, organization_id, account_id)


@router.post("/{organization_id}/leave", status_code=204, responses={403: ERROR, 404: ERROR, 409: ERROR})
async def leave_organization(organization_id: UUID, account: CurrentAccount, service: Service) -> None:
    """Any member but the last Owner (409 `last_owner`); a Pessoal cannot be left (403)."""
    await service.leave(account.id, organization_id)
