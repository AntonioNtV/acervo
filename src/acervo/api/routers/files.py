import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import get_file_service, get_settings, require_api_key
from acervo.core import signing
from acervo.core.settings import Settings
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileLink, FileNodeRead, FileVersionResponse
from acervo.services.file_service import FileService

ERROR: dict[str, Any] = {"model": ErrorResponse}
KEY = [Depends(require_api_key)]

router = APIRouter(prefix="/v1", tags=["files"], responses={401: ERROR, 422: ERROR})

Service = Annotated[FileService, Depends(get_file_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def require_key_or_signature(
    node_id: UUID,
    settings: AppSettings,
    version_id: UUID | None = None,
    expires: int | None = None,
    signature: str | None = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """The key, or a link signed for exactly this content of the file and not yet expired."""
    secret = settings.api_key.get_secret_value()
    if (
        expires is not None
        and signature is not None
        and signing.verify(secret, node_id, version_id, expires, signature, time.time())
    ):
        return
    await require_api_key(settings, x_api_key)


@router.post(
    "/kbs/{kb_id}/files",
    status_code=201,
    response_model=FileNodeRead,
    responses={404: ERROR, 409: ERROR},
    dependencies=KEY,
)
async def upload_file(
    kb_id: UUID,
    file: UploadFile,
    service: Service,
    parent_id: Annotated[UUID | None, Form(description="Folder to save into; omitted for the base's root.")] = None,
) -> FileNodeRead:
    return await service.save(kb_id, parent_id, file.filename, file.file)


@router.post("/nodes/{node_id}/file", response_model=FileNodeRead, responses={404: ERROR, 409: ERROR}, dependencies=KEY)
async def replace_file(node_id: UUID, file: UploadFile, service: Service) -> FileNodeRead:
    return await service.replace(node_id, file.file)


@router.get(
    "/files/{node_id}/versions", response_model=list[FileVersionResponse], responses={404: ERROR}, dependencies=KEY
)
async def list_file_versions(node_id: UUID, service: Service) -> list[FileVersionResponse]:
    return await service.versions(node_id)


@router.post(
    "/files/{node_id}/versions/{version_id}/restore",
    response_model=FileNodeRead,
    responses={404: ERROR, 409: ERROR},
    dependencies=KEY,
)
async def restore_file_version(node_id: UUID, version_id: UUID, service: Service) -> FileNodeRead:
    return await service.restore(node_id, version_id)


@router.post("/files/{node_id}/link", response_model=FileLink, responses={404: ERROR}, dependencies=KEY)
async def file_link(
    node_id: UUID, request: Request, service: Service, settings: AppSettings, version_id: UUID | None = None
) -> FileLink:
    """A link to the file's bytes, or to one older content of it, that opens without the key for 60 seconds."""
    raw_url = str(request.url_for("raw_file", node_id=node_id))
    return await service.link(node_id, version_id, settings.api_key.get_secret_value(), raw_url)


@router.get(
    "/files/{node_id}/raw",
    response_class=StreamingResponse,
    dependencies=[Depends(require_key_or_signature)],
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The original bytes."},
        206: {"content": {"application/octet-stream": {}}, "description": "A range of them."},
        404: ERROR,
        416: {"description": "The range is outside the file."},
    },
)
async def raw_file(
    node_id: UUID,
    service: Service,
    version_id: UUID | None = None,
    range: Annotated[str | None, Header()] = None,
) -> Response:
    """The file byte for byte as uploaded, or one older content of it; one `Range` of bytes is honored.

    Takes the X-API-Key header or the `expires` and `signature` of a link from `POST /v1/files/{node_id}/link`.
    """
    download = await service.download(node_id, version_id, range)
    if download.body is None:
        return Response(status_code=download.status, headers=download.headers)
    return StreamingResponse(
        download.body, status_code=download.status, media_type=download.media_type, headers=download.headers
    )
