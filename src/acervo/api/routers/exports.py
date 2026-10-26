from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from acervo.api.deps import SIGNED_IN, current_session_id, get_export_service, get_settings, session_or_signature
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink
from acervo.services.export_service import ExportService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1", tags=["exports"], responses={401: ERROR, 404: ERROR, 422: ERROR})

Service = Annotated[ExportService, Depends(get_export_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]
SessionId = Annotated[UUID, Depends(current_session_id)]


@router.post("/nodes/{node_id}/export/link", response_model=FileLink, dependencies=SIGNED_IN)
async def export_link(
    node_id: UUID, request: Request, service: Service, settings: AppSettings, session_id: SessionId
) -> FileLink:
    """A link to the zip of a page or folder that opens without the cookie for 60 seconds."""
    raw_url = str(request.url_for("export_node", node_id=node_id))
    return await service.link(node_id, settings.session_secret.get_secret_value(), session_id, raw_url)


@router.get(
    "/nodes/{node_id}/export",
    response_class=StreamingResponse,
    dependencies=[Depends(session_or_signature("export"))],
    responses={200: {"content": {"application/zip": {}}, "description": "The zip, made as it is sent."}},
)
async def export_node(node_id: UUID, service: Service) -> StreamingResponse:
    """A page or folder and everything live under it as a zip: pages as their Markdown text, files as stored.

    Takes the session cookie or a link from `POST /v1/nodes/{node_id}/export/link`.
    A storage error breaks the download off instead of ending it as a shorter zip.
    """
    export = await service.open(node_id)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(export.filename)}"}
    return StreamingResponse(export.body, media_type="application/zip", headers=headers)
