from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import current_account, get_base_service, get_tree_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.kb import KbRead
from acervo.schemas.node import NodeWithPath
from acervo.services.base_service import BaseService
from acervo.services.tree_service import TreeService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/kbs",
    tags=["trash"],
    dependencies=[Depends(current_account)],
    responses={401: ERROR, 422: ERROR},
)


@router.get("/trash", response_model=list[KbRead])
async def list_trashed_kbs(service: Annotated[BaseService, Depends(get_base_service)]) -> list[KbRead]:
    """Bases in the trash, most recently trashed first."""
    return await service.trashed()


@router.get("/{kb_id}/trash", response_model=list[NodeWithPath])
async def list_trash(kb_id: UUID, service: Annotated[TreeService, Depends(get_tree_service)]) -> list[NodeWithPath]:
    """One item per trashing, most recent first, with where it was; what was under it went with it."""
    return await service.trash_of(kb_id)
