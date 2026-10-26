from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import (
    SIGNED_IN,
    current_session_id,
    get_attachment_service,
    get_settings,
    on_node,
    session_or_signature,
)
from acervo.core.settings import Settings
from acervo.schemas.attachment import Attachment
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink
from acervo.services.attachment_service import AttachmentService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1/pages", tags=["attachments"], responses={401: ERROR, 403: ERROR, 404: ERROR, 422: ERROR})

AppSettings = Annotated[Settings, Depends(get_settings)]
SessionId = Annotated[UUID, Depends(current_session_id)]
Service = Annotated[AttachmentService, Depends(get_attachment_service)]
READER = [Depends(on_node("reader"))]
EDITOR = [Depends(on_node("editor"))]


@router.post("/{node_id}/attachments", response_model=Attachment, dependencies=[*SIGNED_IN, *EDITOR])
async def upload_attachment(node_id: UUID, file: UploadFile, service: Service) -> Attachment:
    """Any file of at most 100 MB put in the page, outside the tree; over it is 422 `attachment_too_large`."""
    return await service.upload(node_id, file.filename, file.file)


@router.post("/{node_id}/attachments/{name}/link", response_model=FileLink, dependencies=[*SIGNED_IN, *READER])
async def attachment_link(
    node_id: UUID, name: str, request: Request, service: Service, settings: AppSettings, session_id: SessionId
) -> FileLink:
    """A link to the attachment's bytes that opens without the cookie for 60 seconds."""
    raw_url = str(request.url_for("raw_attachment", node_id=node_id, name=name))
    return await service.link(node_id, name, settings.session_secret.get_secret_value(), session_id, raw_url)


@router.get(
    "/{node_id}/attachments/{name}/raw",
    response_class=StreamingResponse,
    dependencies=[Depends(session_or_signature("attachment")), *READER],
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The bytes as uploaded."},
        206: {"content": {"application/octet-stream": {}}, "description": "A range of them."},
        416: {"description": "The range is outside the file."},
    },
)
async def raw_attachment(
    node_id: UUID,
    name: str,
    service: Service,
    # The attachment a signed link was made for; it comes with the link, never written by hand.
    version_id: Annotated[UUID | None, Query(include_in_schema=False)] = None,
    range: Annotated[str | None, Header()] = None,
) -> Response:
    """The attachment byte for byte; one `Range` of bytes is honored.

    Takes the session cookie or a link from `POST /v1/pages/{node_id}/attachments/{name}/link`.
    """
    download = await service.download(node_id, name, version_id, range)
    if download.body is None:
        return Response(status_code=download.status, headers=download.headers)
    return StreamingResponse(
        download.body, status_code=download.status, media_type=download.media_type, headers=download.headers
    )
