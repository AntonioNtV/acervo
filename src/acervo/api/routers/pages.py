from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from acervo.api.deps import get_page_service, get_settings, require_api_key
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.page import PageDiff, PageRead, PageTextPut, PageTextSaved, PageVersionSummary
from acervo.services.page_service import PageService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1/pages",
    tags=["pages"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[PageService, Depends(get_page_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/{node_id}", response_model=PageRead, responses={404: ERROR})
async def get_page(node_id: UUID, service: Service) -> PageRead:
    return await service.read(node_id)


@router.put("/{node_id}/text", response_model=PageTextSaved, responses={404: ERROR, 409: ERROR})
async def put_page_text(node_id: UUID, body: PageTextPut, service: Service, settings: AppSettings) -> PageTextSaved:
    """Autosave of the working text. A 409 `stale_page` carries the newest `markdown` and `revision` in `details`;
    the refused text was kept as a version."""
    return await service.put_text(node_id, body, settings.version_idle_seconds)


@router.post("/{node_id}/leave", status_code=204, responses={404: ERROR})
async def leave_page(node_id: UUID, service: Service) -> None:
    """The person left the page: the working text becomes a version, unless it already is one."""
    await service.cut(node_id)


@router.get("/{node_id}/versions", response_model=list[PageVersionSummary], responses={404: ERROR})
async def list_page_versions(node_id: UUID, service: Service) -> list[PageVersionSummary]:
    """The page's versions, newest first, without their text; the working text is cut as a version first."""
    return await service.versions(node_id)


@router.get("/{node_id}/versions/{version_id}/diff", response_model=PageDiff, responses={404: ERROR})
async def page_version_diff(node_id: UUID, version_id: UUID, service: Service) -> PageDiff:
    return await service.diff(node_id, version_id)


@router.post("/{node_id}/versions/{version_id}/restore", response_model=PageRead, responses={404: ERROR})
async def restore_page_version(node_id: UUID, version_id: UUID, service: Service) -> PageRead:
    return await service.restore(node_id, version_id)
