from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import CurrentAccount, current_account, get_access_service, get_base_service, get_tree_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.kb import KbRead
from acervo.schemas.node import NodeWithPath
from acervo.services.access_service import AccessService
from acervo.services.base_service import BaseService
from acervo.services.tree_service import TreeService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/kbs",
    tags=["trash"],
    dependencies=[Depends(current_account)],
    responses={401: ERROR, 403: ERROR, 422: ERROR},
)


@router.get("/trash", response_model=list[KbRead])
async def list_trashed_kbs(
    service: Annotated[BaseService, Depends(get_base_service)], organization_id: UUID | None = None
) -> list[KbRead]:
    """Bases of the organization (the Pessoal when none) in the trash where the person is Editor or more, most
    recently trashed first."""
    return await service.trashed(organization_id)


@router.get("/{kb_id}/trash", response_model=list[NodeWithPath], responses={404: ERROR})
async def list_trash(
    kb_id: UUID,
    account: CurrentAccount,
    access: Annotated[AccessService, Depends(get_access_service)],
    service: Annotated[TreeService, Depends(get_tree_service)],
) -> list[NodeWithPath]:
    """One item per trashing, most recent first, with where it was; what was under it went with it. Editor or more."""
    await access.require_base(account.id, kb_id, "editor")
    return await service.trash_of(kb_id)
