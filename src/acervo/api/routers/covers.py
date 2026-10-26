from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import SIGNED_IN, current_session_id, get_cover_service, get_settings, session_or_signature
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink
from acervo.schemas.node import NodeRead
from acervo.services.cover_service import CoverService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1", tags=["covers"], responses={401: ERROR, 404: ERROR, 422: ERROR})

AppSettings = Annotated[Settings, Depends(get_settings)]
SessionId = Annotated[UUID, Depends(current_session_id)]
Service = Annotated[CoverService, Depends(get_cover_service)]


@router.post("/nodes/{node_id}/cover", response_model=NodeRead, dependencies=SIGNED_IN)
async def upload_cover(node_id: UUID, file: UploadFile, service: Service) -> NodeRead:
    """A PNG, JPEG or WebP image of at most 10 MB becomes the cover of a folder or page."""
    return await service.upload(node_id, file.file)


@router.post("/nodes/{node_id}/cover/link", response_model=FileLink, dependencies=SIGNED_IN)
async def cover_link(
    node_id: UUID, request: Request, service: Service, settings: AppSettings, session_id: SessionId
) -> FileLink:
    """A link to the node's uploaded cover image that opens without the cookie for 60 seconds."""
    raw_url = str(request.url_for("raw_cover", node_id=node_id))
    return await service.link(node_id, settings.session_secret.get_secret_value(), session_id, raw_url)


@router.get(
    "/nodes/{node_id}/cover/raw",
    response_class=StreamingResponse,
    dependencies=[Depends(session_or_signature("cover"))],
    responses={200: {"content": {"image/*": {}}, "description": "The image as uploaded."}},
)
async def raw_cover(node_id: UUID, service: Service) -> StreamingResponse:
    """The node's uploaded cover image.

    Takes the session cookie or a link from `POST /v1/nodes/{node_id}/cover/link`.
    """
    image = await service.open(node_id)
    # Every link is a new URL, so the browser may keep what one served.
    headers = {"Cache-Control": "private, max-age=31536000, immutable"}
    return StreamingResponse(image.body, media_type=image.media_type, headers=headers)
