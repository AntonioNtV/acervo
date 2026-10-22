from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import get_page_service, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.page import DraftPut, PageDiff, PageDraftRead, PageRead, PageSave, PageVersionSummary
from acervo.services.page_service import PageService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/pages",
    tags=["pages"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[PageService, Depends(get_page_service)]


@router.get("/{node_id}", response_model=PageRead, responses={404: ERROR})
async def get_page(node_id: UUID, service: Service) -> PageRead:
    return await service.read(node_id)


@router.put("/{node_id}", response_model=PageVersionSummary, responses={404: ERROR, 409: ERROR})
async def save_page(node_id: UUID, body: PageSave, service: Service) -> PageVersionSummary:
    """A new whole-file version. A 409 `stale_page` carries the current version, its text and the diff from the base
    in `details`."""
    return await service.save(node_id, body)


@router.put("/{node_id}/draft", response_model=PageDraftRead, responses={404: ERROR})
async def put_draft(node_id: UUID, body: DraftPut, service: Service) -> PageDraftRead:
    return await service.put_draft(node_id, body)


@router.delete("/{node_id}/draft", status_code=204, responses={404: ERROR})
async def discard_draft(node_id: UUID, service: Service) -> None:
    await service.discard_draft(node_id)


@router.get("/{node_id}/versions", response_model=list[PageVersionSummary], responses={404: ERROR})
async def list_page_versions(node_id: UUID, service: Service) -> list[PageVersionSummary]:
    """The page's versions, newest first, without their text."""
    return await service.versions(node_id)


@router.get("/{node_id}/versions/{version_id}/diff", response_model=PageDiff, responses={404: ERROR})
async def page_version_diff(node_id: UUID, version_id: UUID, service: Service) -> PageDiff:
    return await service.diff(node_id, version_id)


@router.post("/{node_id}/versions/{version_id}/restore", response_model=PageRead, responses={404: ERROR})
async def restore_page_version(node_id: UUID, version_id: UUID, service: Service) -> PageRead:
    return await service.restore(node_id, version_id)
