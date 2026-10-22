import re
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, Response, UploadFile
from fastapi.responses import StreamingResponse

from acervo.api.deps import get_file_service, require_api_key
from acervo.schemas.common import ErrorResponse
from acervo.schemas.file import FileNodeRead, FileVersionRead
from acervo.services.file_service import FileService

ERROR: dict[str, Any] = {"model": ErrorResponse}

router = APIRouter(
    prefix="/v1",
    tags=["files"],
    dependencies=[Depends(require_api_key)],
    responses={401: ERROR, 422: ERROR},
)

Service = Annotated[FileService, Depends(get_file_service)]

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@router.post("/kbs/{kb_id}/files", status_code=201, response_model=FileNodeRead, responses={404: ERROR, 409: ERROR})
async def upload_file(
    kb_id: UUID,
    file: UploadFile,
    service: Service,
    parent_id: Annotated[UUID | None, Form(description="Folder to save into; omitted for the base's root.")] = None,
) -> FileNodeRead:
    return await service.save(kb_id, parent_id, file.filename, file.file)


@router.post("/nodes/{node_id}/file", response_model=FileNodeRead, responses={404: ERROR, 409: ERROR})
async def replace_file(node_id: UUID, file: UploadFile, service: Service) -> FileNodeRead:
    return await service.replace(node_id, file.file)


@router.get("/files/{node_id}/versions", response_model=list[FileVersionRead], responses={404: ERROR})
async def list_file_versions(node_id: UUID, service: Service) -> list[FileVersionRead]:
    return await service.versions(node_id)


@router.post(
    "/files/{node_id}/versions/{version_id}/restore",
    response_model=FileNodeRead,
    responses={404: ERROR, 409: ERROR},
)
async def restore_file_version(node_id: UUID, version_id: UUID, service: Service) -> FileNodeRead:
    return await service.restore(node_id, version_id)


@router.get(
    "/files/{node_id}/raw",
    response_class=StreamingResponse,
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
    """The file byte for byte as uploaded, or one older content of it; one `Range` of bytes is honored."""
    node, content = await service.open(node_id, version_id)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(node.title)}",
        "ETag": f'"{content.sha256}"',
    }
    # A malformed or multi-part Range is ignored and the whole file is served, as RFC 9110 allows.
    match = _RANGE.fullmatch(range.strip()) if range else None
    if match is None or match.groups() == ("", ""):
        headers["Content-Length"] = str(content.size)
        return StreamingResponse(service.stream(content), media_type=content.mime, headers=headers)
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last), content.size - 1) if last else content.size - 1
    else:
        start, end = max(content.size - int(last), 0), content.size - 1
    if start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{content.size}"})
    headers["Content-Range"] = f"bytes {start}-{end}/{content.size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        service.stream(content, (start, end)), status_code=206, media_type=content.mime, headers=headers
    )
