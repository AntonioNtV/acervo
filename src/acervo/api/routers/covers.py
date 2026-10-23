import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import get_settings, get_storage, get_uow, require_api_key
from acervo.core import signing
from acervo.core.settings import Settings
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink
from acervo.schemas.node import NodeRead
from acervo.services.cover_service import CoverService
from acervo.services.storage import Storage

ERROR: dict[str, Any] = {"model": ErrorResponse}
KEY = [Depends(require_api_key)]

router = APIRouter(prefix="/v1", tags=["covers"], responses={401: ERROR, 404: ERROR, 422: ERROR})

AppSettings = Annotated[Settings, Depends(get_settings)]


def get_cover_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    storage: Annotated[Storage, Depends(get_storage)],
    settings: AppSettings,
) -> CoverService:
    return CoverService(uow, storage, settings.cover_max_bytes)


Service = Annotated[CoverService, Depends(get_cover_service)]


async def require_key_or_cover_signature(
    node_id: UUID,
    settings: AppSettings,
    expires: int | None = None,
    signature: str | None = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """The key, or a link signed for this node's cover and not yet expired."""
    secret = settings.api_key.get_secret_value()
    if (
        expires is not None
        and signature is not None
        and signing.verify(secret, "cover", node_id, None, expires, signature, time.time())
    ):
        return
    await require_api_key(settings, x_api_key)


@router.post("/nodes/{node_id}/cover", response_model=NodeRead, dependencies=KEY)
async def upload_cover(node_id: UUID, file: UploadFile, service: Service) -> NodeRead:
    """A PNG, JPEG or WebP image of at most 10 MB becomes the cover of a folder or page."""
    return await service.upload(node_id, file.file)


@router.post("/nodes/{node_id}/cover/link", response_model=FileLink, dependencies=KEY)
async def cover_link(node_id: UUID, request: Request, service: Service, settings: AppSettings) -> FileLink:
    """A link to the node's uploaded cover image that opens without the key for 60 seconds."""
    raw_url = str(request.url_for("raw_cover", node_id=node_id))
    return await service.link(node_id, settings.api_key.get_secret_value(), raw_url)


@router.get(
    "/nodes/{node_id}/cover/raw",
    response_class=StreamingResponse,
    dependencies=[Depends(require_key_or_cover_signature)],
    responses={200: {"content": {"image/*": {}}, "description": "The image as uploaded."}},
)
async def raw_cover(node_id: UUID, service: Service) -> StreamingResponse:
    """The node's uploaded cover image.

    Takes the X-API-Key header or the `expires` and `signature` of a link from `POST /v1/nodes/{node_id}/cover/link`.
    """
    image = await service.open(node_id)
    # Every link is a new URL, so the browser may keep what one served.
    headers = {"Cache-Control": "private, max-age=31536000, immutable"}
    return StreamingResponse(image.body, media_type=image.media_type, headers=headers)
