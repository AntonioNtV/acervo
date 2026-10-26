import csv
import io
import json
from pathlib import PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import (
    SIGNED_IN,
    CurrentAccount,
    RecentSignIn,
    get_deletion_service,
    get_organization_service,
    get_security_log,
)
from acervo.schemas.common import ErrorResponse
from acervo.schemas.organization import (
    MemberRead,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    RoleChange,
)
from acervo.schemas.security import AuditEventRead
from acervo.services.deletion_service import DeletionService
from acervo.services.organization_service import OrganizationService
from acervo.services.security_log import SecurityLog

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/organizations",
    tags=["organizations"],
    dependencies=SIGNED_IN,
    responses={401: ERROR, 422: ERROR},
)


Service = Annotated[OrganizationService, Depends(get_organization_service)]
Deletion = Annotated[DeletionService, Depends(get_deletion_service)]
Log = Annotated[SecurityLog, Depends(get_security_log)]
# A cell starting like a formula runs as one in a spreadsheet; names and emails are typed by anyone.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_STARTS) else text


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
    """Owners and Admins; a Pessoal keeps its name and requires nothing. Turning `require_two_factor` on emails the
    members who sign in with a password only; `password_only` says how many remain."""
    return await service.update(account.id, organization_id, body)


@router.delete("/{organization_id}", status_code=204, responses={403: ERROR, 404: ERROR})
async def delete_organization(
    organization_id: UUID, account: CurrentAccount, _: RecentSignIn, service: Deletion
) -> None:
    """Owners only, with a recent sign-in (403 `reauthentication_required`); a Pessoal goes only with its account
    (403 `personal_org`). Its bases go with every page, file and version, never through the trash; every other
    member is told by email."""
    await service.delete_organization(account.id, organization_id)


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


@router.get("/{organization_id}/audit", response_model=list[AuditEventRead], responses={403: ERROR})
async def audit(organization_id: UUID, account: CurrentAccount, log: Log) -> list[AuditEventRead]:
    """Organização › Auditoria, for Owners and Admins: the last 90 days, newest first."""
    return await log.audit(account.id, organization_id)


@router.get(
    "/{organization_id}/audit.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The audit as CSV."}, 403: ERROR},
)
async def audit_csv(organization_id: UUID, account: CurrentAccount, log: Log) -> Response:
    """The audit of `GET /audit` as a CSV download (Exportar CSV)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["created_at", "kind", "actor_name", "actor_email", "data"])
    for event in await log.audit(account.id, organization_id):
        row = [event.created_at.isoformat(), event.kind, event.actor_name, event.actor_email, json.dumps(event.data)]
        writer.writerow([_cell(value) for value in row])
    headers = {"Content-Disposition": 'attachment; filename="auditoria.csv"'}
    return Response(out.getvalue(), media_type="text/csv", headers=headers)
