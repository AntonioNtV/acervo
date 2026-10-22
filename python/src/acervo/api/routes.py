import re
import uuid
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Header, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.api.models import (
    CreateKbRequest,
    CreateNodeRequest,
    DiffResponse,
    DraftResponse,
    ErrorResponse,
    FileResponse,
    KbResponse,
    KbSummaryResponse,
    MoveNodeRequest,
    NodeDetailResponse,
    NodeResponse,
    PageResponse,
    PutDraftRequest,
    RenameNodeRequest,
    RestoredNodeResponse,
    SavePageRequest,
    SearchHitResponse,
    SectionResponse,
    StalePageResponse,
    TrashItemResponse,
    TreeNodeResponse,
    UpdateKbRequest,
    VersionResponse,
)
from acervo.config import Settings
from acervo.errors import NotFoundError, ValidationError
from acervo.pages import drafts, links
from acervo.pages import versions as page_versions
from acervo.pages.diff import line_diff
from acervo.pages.sections import sections
from acervo.pdfs import files
from acervo.pdfs import versions as file_versions
from acervo.pdfs.storage import Storage
from acervo.store.db import get_session
from acervo.store.models import File, Node, PageVersion
from acervo.store.repositories import get, path
from acervo.tree import kbs, nodes, search, trash

router = APIRouter(
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    }
)

Session = Annotated[AsyncSession, Depends(get_session)]


@lru_cache
def storage() -> Storage:
    return Storage(Settings())


Bucket = Annotated[Storage, Depends(storage)]


# Bases


@router.get("/kbs")
async def list_kbs(session: Session, q: str = "") -> list[KbSummaryResponse]:
    return [
        KbSummaryResponse(
            **KbResponse.model_validate(row.kb).model_dump(), pages=row.pages, files=row.files, last_edit=row.last_edit
        )
        for row in await kbs.list_kbs(session, q)
    ]


@router.post("/kbs", status_code=status.HTTP_201_CREATED)
async def create_kb(session: Session, body: CreateKbRequest) -> KbResponse:
    kb = await kbs.create_kb(session, body.name, body.description)
    await session.commit()
    return KbResponse.model_validate(kb)


@router.patch("/kbs/{kb_id}")
async def update_kb(session: Session, kb_id: uuid.UUID, body: UpdateKbRequest) -> KbResponse:
    kb = await kbs.update_kb(session, kb_id, body.name, body.description)
    await session.commit()
    return KbResponse.model_validate(kb)


@router.delete("/kbs/{kb_id}")
async def trash_kb(session: Session, kb_id: uuid.UUID) -> KbResponse:
    kb = await kbs.trash_kb(session, kb_id)
    await session.commit()
    return KbResponse.model_validate(kb)


@router.get("/trash/kbs")
async def list_trashed_kbs(session: Session) -> list[KbResponse]:
    return [KbResponse.model_validate(kb) for kb in await kbs.list_trashed_kbs(session)]


@router.post("/kbs/{kb_id}/restore")
async def restore_kb(session: Session, kb_id: uuid.UUID) -> KbResponse:
    kb = await kbs.restore_kb(session, kb_id)
    await session.commit()
    return KbResponse.model_validate(kb)


# The tree


@router.get("/kbs/{kb_id}/children")
async def children(session: Session, kb_id: uuid.UUID, parent_id: uuid.UUID | None = None) -> list[TreeNodeResponse]:
    found = await nodes.children(session, kb_id, parent_id)
    file_ids = [node.id for node in found if node.kind == "file"]
    protected = set(await session.scalars(select(File.node_id).where(File.node_id.in_(file_ids), File.protected)))
    return [
        TreeNodeResponse(**NodeResponse.model_validate(node).model_dump(), protected=node.id in protected)
        for node in found
    ]


@router.get("/kbs/{kb_id}/search")
async def search_nodes(session: Session, kb_id: uuid.UUID, q: str) -> list[SearchHitResponse]:
    return [
        SearchHitResponse(**NodeResponse.model_validate(hit.node).model_dump(), path=hit.path)
        for hit in await search.search(session, kb_id, q)
    ]


@router.get("/kbs/{kb_id}/trash")
async def list_trash(session: Session, kb_id: uuid.UUID) -> list[TrashItemResponse]:
    return [
        TrashItemResponse(**NodeResponse.model_validate(item.node).model_dump(), path=item.path)
        for item in await trash.list_trash(session, kb_id)
    ]


@router.post("/kbs/{kb_id}/nodes", status_code=status.HTTP_201_CREATED)
async def create_node(session: Session, kb_id: uuid.UUID, body: CreateNodeRequest) -> NodeResponse:
    node = await nodes.create(session, kb_id, body.parent_id, body.kind, body.title)
    if node.kind == "page":
        await page_versions.create(session, node)
    await session.commit()
    return NodeResponse.model_validate(node)


@router.patch("/nodes/{node_id}")
async def rename_node(session: Session, node_id: uuid.UUID, body: RenameNodeRequest) -> NodeResponse:
    node = await nodes.live_node(session, node_id)
    title = " ".join(body.title.split())
    if node.kind == "page" and title and title != node.title:
        await links.fix_links(session, node, title)
    await nodes.rename(session, node_id, body.title)
    await session.commit()
    return NodeResponse.model_validate(node)


@router.post("/nodes/{node_id}/move")
async def move_node(session: Session, node_id: uuid.UUID, body: MoveNodeRequest) -> NodeResponse:
    node = await nodes.move(session, node_id, body.parent_id, body.before_id)
    await session.commit()
    return NodeResponse.model_validate(node)


@router.delete("/nodes/{node_id}")
async def trash_node(session: Session, node_id: uuid.UUID) -> NodeResponse:
    node = await trash.trash(session, node_id)
    await session.commit()
    return NodeResponse.model_validate(node)


@router.post("/nodes/{node_id}/restore")
async def restore_node(session: Session, node_id: uuid.UUID) -> RestoredNodeResponse:
    restored = await trash.restore(session, node_id)
    await session.commit()
    return RestoredNodeResponse(**NodeResponse.model_validate(restored.node).model_dump(), to_root=restored.to_root)


# Pages and files


async def _detail(session: AsyncSession, node: Node) -> NodeDetailResponse:
    page = file = None
    count = 0
    if node.kind == "page":
        version = await page_versions.current(session, node.id)
        draft = await drafts.get(session, node.id)
        page = PageResponse(
            version_id=version.id,
            markdown=version.markdown,
            draft=draft and DraftResponse.model_validate(draft),
            links=await links.resolve(session, node),
            sections=[SectionResponse(anchor=s.anchor, heading=s.heading) for s in sections(version.markdown)],
        )
        count = await session.scalar(select(func.count()).where(PageVersion.node_id == node.id)) or 0
    elif node.kind == "file":
        file = FileResponse.model_validate(await file_versions.current(session, node.id))
        count = len(await file_versions.list_versions(session, node.id)) + 1
    return NodeDetailResponse(
        **NodeResponse.model_validate(node).model_dump(),
        path=await path(session, node.id),
        page=page,
        file=file,
        versions=count,
    )


async def _page(session: AsyncSession, node_id: uuid.UUID) -> Node:
    node = await nodes.live_node(session, node_id)
    if node.kind != "page":
        raise ValidationError(f"node {node_id} is not a page")
    return node


@router.get("/nodes/{node_id}")
async def get_node(session: Session, node_id: uuid.UUID) -> NodeDetailResponse:
    return await _detail(session, await nodes.live_node(session, node_id))


@router.put("/nodes/{node_id}", responses={status.HTTP_409_CONFLICT: {"model": StalePageResponse}})
async def save_page(session: Session, node_id: uuid.UUID, body: SavePageRequest) -> VersionResponse:
    node = await _page(session, node_id)
    version = await page_versions.save(session, node, body.markdown, body.base_version_id, force=body.force)
    await session.commit()
    return VersionResponse(id=version.id, created_at=version.created_at, author=version.author, size=None)


@router.put("/nodes/{node_id}/draft")
async def put_draft(session: Session, node_id: uuid.UUID, body: PutDraftRequest) -> DraftResponse:
    await _page(session, node_id)
    draft = await drafts.put(session, node_id, body.markdown, body.base_version_id)
    await session.commit()
    return DraftResponse.model_validate(draft)


@router.delete("/nodes/{node_id}/draft", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(session: Session, node_id: uuid.UUID) -> None:
    await _page(session, node_id)
    await drafts.discard(session, node_id)
    await session.commit()


@router.get("/nodes/{node_id}/versions")
async def list_versions(session: Session, node_id: uuid.UUID) -> list[VersionResponse]:
    """A page's versions, newest first. A file's older contents, newest first; its current one is the node."""
    node = await nodes.live_node(session, node_id)
    if node.kind == "page":
        return [
            VersionResponse(id=v.id, created_at=v.created_at, author=v.author, size=None)
            for v in await page_versions.history(session, node.id)
        ]
    if node.kind == "file":
        return [
            VersionResponse(id=v.id, created_at=v.replaced_at, author=None, size=v.size)
            for v in await file_versions.list_versions(session, node.id)
        ]
    raise ValidationError(f"node {node_id} has no versions")


@router.get("/nodes/{node_id}/versions/{version_id}/diff")
async def version_diff(session: Session, node_id: uuid.UUID, version_id: uuid.UUID) -> DiffResponse:
    node = await _page(session, node_id)
    version = await get(session, PageVersion, version_id)
    if version.node_id != node.id:
        raise NotFoundError(f"page_version {version_id} not found")
    previous = await page_versions.previous_markdown(session, version)
    return DiffResponse.model_validate({"lines": line_diff(previous, version.markdown)})


@router.post("/nodes/{node_id}/versions/{version_id}/restore")
async def restore_version(session: Session, node_id: uuid.UUID, version_id: uuid.UUID) -> NodeDetailResponse:
    node = await nodes.live_node(session, node_id)
    if node.kind == "page":
        if (await get(session, PageVersion, version_id)).node_id != node.id:
            raise NotFoundError(f"page_version {version_id} not found")
        await page_versions.restore(session, version_id)
    elif node.kind == "file":
        await file_versions.restore(session, node.id, version_id)
    else:
        raise ValidationError(f"node {node_id} has no versions")
    await session.commit()
    return await _detail(session, node)


@router.post("/kbs/{kb_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    session: Session,
    bucket: Bucket,
    kb_id: uuid.UUID,
    file: UploadFile,
    parent_id: Annotated[uuid.UUID | None, Form()] = None,
) -> NodeDetailResponse:
    if not file.filename:
        raise ValidationError("the file has no name")
    saved = await files.save(session, bucket, kb_id, parent_id, file.filename, file.file)
    await session.commit()
    return await _detail(session, await nodes.live_node(session, saved.node_id))


@router.post("/nodes/{node_id}/file")
async def replace_file(session: Session, bucket: Bucket, node_id: uuid.UUID, file: UploadFile) -> NodeDetailResponse:
    node = await nodes.live_node(session, node_id)
    await file_versions.replace(session, bucket, node.id, file.file)
    await session.commit()
    return await _detail(session, node)


_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get(
    "/files/{node_id}/raw",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {"content": {"application/octet-stream": {}}, "description": "The original bytes."},
        status.HTTP_206_PARTIAL_CONTENT: {"content": {"application/octet-stream": {}}, "description": "A range."},
        status.HTTP_416_RANGE_NOT_SATISFIABLE: {"description": "The range is outside the file."},
    },
)
async def raw_file(
    session: Session,
    bucket: Bucket,
    node_id: uuid.UUID,
    version_id: uuid.UUID | None = None,
    range: Annotated[str | None, Header()] = None,
) -> Response:
    """The file byte for byte as uploaded, or one older content of it; one `Range` of bytes is honored."""
    node = await nodes.live_node(session, node_id)
    row, chunks = await file_versions.open_bytes(session, bucket, node.id, version_id)
    headers: dict[str, Any] = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(node.title)}",
        "ETag": f'"{row.sha256}"',
    }
    # A malformed or multi-part Range is ignored and the whole file is served, as RFC 9110 allows.
    match = _RANGE.fullmatch(range.strip()) if range else None
    # The bytes come from the bucket; the database is not held while they are sent.
    await session.close()
    if match is None or match.groups() == ("", ""):
        return StreamingResponse(chunks, media_type=row.mime, headers={**headers, "Content-Length": str(row.size)})
    first, last = match.groups()
    if first:
        start, end = int(first), min(int(last), row.size - 1) if last else row.size - 1
    else:
        start, end = max(row.size - int(last), 0), row.size - 1
    if start > end:
        return Response(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE, headers={"Content-Range": f"bytes */{row.size}"}
        )
    headers["Content-Range"] = f"bytes {start}-{end}/{row.size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        bucket.stream(row.storage_key, (start, end)),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=row.mime,
        headers=headers,
    )
