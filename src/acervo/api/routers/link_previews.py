from typing import Annotated, Any

from fastapi import APIRouter, Depends

from acervo.api.deps import SIGNED_IN, get_link_preview_service
from acervo.schemas.common import ErrorResponse
from acervo.schemas.link_preview import LinkPreview
from acervo.services.link_preview_service import LinkPreviewService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1", tags=["link-previews"], responses={401: ERROR, 422: ERROR})

Service = Annotated[LinkPreviewService, Depends(get_link_preview_service)]


@router.get("/link-preview", response_model=LinkPreview, dependencies=SIGNED_IN)
async def link_preview(url: str, service: Service) -> LinkPreview:
    """The site's title, description and image, read by the server within 5 seconds and 1 MB.

    A site that fails or is too slow gives only `url` and `domain`. A URL that is not http(s), or whose host or any
    redirect points to a loopback, private, link-local, multicast or reserved address, is 422 `link_not_allowed`.
    """
    return await service.preview(url)
