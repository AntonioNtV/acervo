from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from acervo.api.deps import CurrentAccount, get_invite_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.organization import InviteCreate, InviteRead
from acervo.services.invite_service import InvitePreview, InviteService

ERROR: dict[str, Any] = {"model": ErrorResponse}

# No session on the router: the Convite screen reads an invite by its token before anyone signs in.
router = APIRouter(tags=["invites"], responses={422: ERROR})

Service = Annotated[InviteService, Depends(get_invite_service)]


class InviteAccept(BaseModel):
    token: str = Field(description="The token of the link /convite/{token}.")


@router.post(
    "/v1/organizations/{organization_id}/invites",
    status_code=201,
    response_model=list[InviteRead],
    responses={401: ERROR, 403: ERROR, 404: ERROR, 409: ERROR},
)
async def invite_to_organization(
    organization_id: UUID, body: InviteCreate, account: CurrentAccount, service: Service
) -> list[InviteRead]:
    """Emails each address a 7-day link; 409 `already_member` names the emails already in the organization."""
    return await service.invite_to_organization(account.id, organization_id, body)


@router.get(
    "/v1/organizations/{organization_id}/invites",
    response_model=list[InviteRead],
    responses={401: ERROR, 403: ERROR},
)
async def organization_invites(organization_id: UUID, account: CurrentAccount, service: Service) -> list[InviteRead]:
    """Invites not yet accepted nor revoked, expired ones included."""
    return await service.pending_for_organization(account.id, organization_id)


@router.post(
    "/v1/kbs/{kb_id}/invites",
    status_code=201,
    response_model=list[InviteRead],
    responses={401: ERROR, 403: ERROR, 404: ERROR},
)
async def invite_to_base(
    kb_id: UUID, body: InviteCreate, account: CurrentAccount, service: Service
) -> list[InviteRead]:
    """Adds members of the base's organization at once; anyone else gets an invite, which this answers."""
    return await service.invite_to_base(account.id, kb_id, body)


@router.get("/v1/kbs/{kb_id}/invites", response_model=list[InviteRead], responses={401: ERROR, 403: ERROR})
async def base_invites(kb_id: UUID, account: CurrentAccount, service: Service) -> list[InviteRead]:
    """Invites to the base not yet accepted nor revoked, expired ones included."""
    return await service.pending_for_base(account.id, kb_id)


@router.post(
    "/v1/invites/{invite_id}/resend",
    response_model=InviteRead,
    responses={401: ERROR, 403: ERROR, 404: ERROR, 429: ERROR},
)
async def resend_invite(invite_id: UUID, account: CurrentAccount, service: Service) -> InviteRead:
    """A new 7-day link, the old one no longer valid; 429 within a minute of the last one."""
    return await service.resend(account.id, invite_id)


@router.delete("/v1/invites/{invite_id}", status_code=204, responses={401: ERROR, 403: ERROR, 404: ERROR})
async def revoke_invite(invite_id: UUID, account: CurrentAccount, service: Service) -> None:
    await service.revoke(account.id, invite_id)


@router.get("/v1/invites/by-token/{token}", response_model=InvitePreview)
async def invite_by_token(token: str, service: Service) -> InvitePreview:
    """What the Convite screen shows, without a session; 422 `code_invalid` for a revoked or used link."""
    return await service.preview(token)


@router.post("/v1/invites/accept", response_model=InvitePreview, responses={401: ERROR})
async def accept_invite(body: InviteAccept, account: CurrentAccount, service: Service) -> InvitePreview:
    """Joins with the invite's role; 422 `invite_email_mismatch` when signed in with another email."""
    return await service.accept(account.id, body.token)
