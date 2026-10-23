import time
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from acervo.api.deps import get_export_service, get_settings, require_api_key
from acervo.core import signing
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink
from acervo.services.export_service import ExportService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(prefix="/v1", tags=["exports"], responses={401: ERROR, 404: ERROR, 422: ERROR})

Service = Annotated[ExportService, Depends(get_export_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def require_key_or_export_signature(
    node_id: UUID,
    settings: AppSettings,
    expires: int | None = None,
    signature: str | None = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """The key, or a link signed for this node's export and not yet expired."""
    secret = settings.api_key.get_secret_value()
    if (
        expires is not None
        and signature is not None
        and signing.verify(secret, "export", node_id, None, expires, signature, time.time())
    ):
        return
    await require_api_key(settings, x_api_key)


@router.post("/nodes/{node_id}/export/link", response_model=FileLink, dependencies=[Depends(require_api_key)])
async def export_link(node_id: UUID, request: Request, service: Service, settings: AppSettings) -> FileLink:
    """A link to the zip of a page or folder that opens without the key for 60 seconds."""
    raw_url = str(request.url_for("export_node", node_id=node_id))
    return await service.link(node_id, settings.api_key.get_secret_value(), raw_url)


@router.get(
    "/nodes/{node_id}/export",
    response_class=StreamingResponse,
    dependencies=[Depends(require_key_or_export_signature)],
    responses={200: {"content": {"application/zip": {}}, "description": "The zip, made as it is sent."}},
)
async def export_node(node_id: UUID, service: Service) -> StreamingResponse:
    """A page or folder and everything live under it as a zip: pages as their Markdown text, files as stored.

    Takes the X-API-Key header or the `expires` and `signature` of a link from `POST /v1/nodes/{node_id}/export/link`.
    A storage error breaks the download off instead of ending it as a shorter zip.
    """
    export = await service.open(node_id)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(export.filename)}"}
    return StreamingResponse(export.body, media_type="application/zip", headers=headers)
