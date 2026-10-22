import asyncio
import hashlib
import mimetypes
import shutil
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from acervo.core.errors import Duplicate, NotFoundError, SameFile, TitleTaken, ValidationError
from acervo.domain.sort_keys import key_between
from acervo.pipeline.pdf import reader
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.file import FileContent, FileCreate, FileNodeRead, FileVersionCreate, FileVersionRead
from acervo.schemas.node import NodeCreate, NodeRead
from acervo.services.storage import Storage, key_for

CHUNK_SIZE = 1024 * 1024
PDF = "application/pdf"


def _hash(source: BinaryIO) -> tuple[str, int, bytes]:
    digest = hashlib.sha256()
    size = 0
    head = b""
    source.seek(0)
    while chunk := source.read(CHUNK_SIZE):
        if size == 0:
            head = chunk[:4]
        digest.update(chunk)
        size += len(chunk)
    source.seek(0)
    return digest.hexdigest(), size, head


def _pdf_metadata(source: BinaryIO) -> reader.PdfMetadata:
    # PyMuPDF opens a path; opening the bytes would hold the whole file in memory.
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / "upload.pdf"
        with copy.open("wb") as target:
            shutil.copyfileobj(source, target, CHUNK_SIZE)
        source.seek(0)
        return reader.metadata(copy)


async def _stage(kb_id: UUID, source: BinaryIO, filename: str) -> FileContent:
    """Reads `source` in chunks where it is, never whole in memory, and leaves it at its start."""
    sha256, size, head = await asyncio.to_thread(_hash, source)
    if head == b"%PDF":
        meta = await asyncio.to_thread(_pdf_metadata, source)
        mime, pages, protected = PDF, meta.pages, meta.protected
    else:
        guessed = mimetypes.guess_type(filename)[0]
        mime = guessed if guessed and guessed != PDF else "application/octet-stream"
        pages, protected = None, False
    return FileContent(
        storage_key=key_for(kb_id, sha256),
        sha256=sha256,
        size=size,
        mime=mime,
        pages=pages,
        protected=protected,
        # Known only once F2 reads the new content; never carried over from a replaced one.
        doc_type=None,
        sensitive=False,
        map=None,
        map_origin=None,
    )


class FileService:
    """Stored files: upload, new versions, history and reading the bytes back."""

    def __init__(self, uow: UnitOfWork, storage: Storage) -> None:
        self._uow = uow
        self._storage = storage

    async def save(self, kb_id: UUID, folder_id: UUID | None, filename: str | None, source: BinaryIO) -> FileNodeRead:
        """Stores a file byte for byte into a folder of the base, as the last of its siblings."""
        if not filename:
            raise ValidationError("the file has no name")
        content = await _stage(kb_id, source, filename)
        await self._uow.kbs.lock(kb_id)
        await self._uow.nodes.live_folder(kb_id, folder_id)
        await self._refuse_duplicate(kb_id, content.sha256)
        if await self._uow.nodes.title_taken(kb_id, folder_id, "file", filename):
            raise TitleTaken("já existe", {"title": filename})
        await self._storage.put(content.storage_key, source, content.size)
        last = await self._uow.nodes.last_sort(kb_id, folder_id)
        node = await self._uow.nodes.create(
            NodeCreate(kb_id=kb_id, parent_id=folder_id, kind="file", title=filename, sort=key_between(last, None))
        )
        await self._uow.files.create(FileCreate(node_id=node.id, **content.model_dump()))
        return await self._commit(node)

    async def replace(self, node_id: UUID, source: BinaryIO) -> FileNodeRead:
        """The file node gets new content; the current one goes to its history."""
        node = await self._file_node(node_id)
        content = await _stage(node.kb_id, source, node.title)
        await self._uow.kbs.lock(node.kb_id)
        current = await self._uow.files.of_node(node.id)
        if content.sha256 == current.sha256:
            raise SameFile("é o mesmo arquivo", {"node_id": str(node.id)})
        await self._refuse_duplicate(node.kb_id, content.sha256, other_than=node.id)
        await self._storage.put(content.storage_key, source, content.size)
        await self._to_history(node.id, current)
        await self._uow.files.set_content(current.id, content)
        return await self._commit(node)

    async def versions(self, node_id: UUID) -> list[FileVersionRead]:
        """The file's older contents, newest first; its current one is the node's."""
        node = await self._file_node(node_id)
        return await self._uow.file_versions.history(node.id)

    async def restore(self, node_id: UUID, version_id: UUID) -> FileNodeRead:
        """An old content becomes current again; the current one goes to history and no version is removed."""
        node = await self._file_node(node_id)
        version = await self._version(node.id, version_id)
        current = await self._uow.files.of_node(node.id)
        if version.sha256 == current.sha256:
            raise SameFile("é o mesmo arquivo", {"node_id": str(node.id)})
        await self._to_history(node.id, current)
        await self._uow.files.set_content(current.id, version)
        return await self._commit(node)

    async def open(self, node_id: UUID, version_id: UUID | None = None) -> tuple[NodeRead, FileContent]:
        """The node and the metadata of its current content, or of one older content of it."""
        node = await self._file_node(node_id)
        content: FileContent = (
            await self._uow.files.of_node(node.id) if version_id is None else await self._version(node.id, version_id)
        )
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        return node, content

    def stream(self, content: FileContent, byte_range: tuple[int, int] | None = None) -> AsyncIterator[bytes]:
        """The stored bytes, or bytes `start` to `end` of them, both included."""
        return self._storage.stream(content.storage_key, byte_range)

    async def _file_node(self, node_id: UUID) -> NodeRead:
        node = await self._uow.nodes.get(node_id)
        if node.deleted_at is not None or node.kind != "file":
            raise NotFoundError(f"file {node_id} not found", {"id": str(node_id)})
        return node

    async def _version(self, node_id: UUID, version_id: UUID) -> FileVersionRead:
        version = await self._uow.file_versions.get(version_id)
        if version.node_id != node_id:
            raise NotFoundError(f"file_version {version_id} not found", {"id": str(version_id)})
        return version

    async def _to_history(self, node_id: UUID, current: FileContent) -> None:
        await self._uow.file_versions.create(
            FileVersionCreate(node_id=node_id, replaced_at=datetime.now(UTC), **current.only_content().model_dump())
        )

    async def _refuse_duplicate(self, kb_id: UUID, sha256: str, other_than: UUID | None = None) -> None:
        """Refuses content the base already holds: in a file, in the trash, or in any file's history."""
        holder = await self._uow.files.holder(kb_id, sha256, other_than)
        in_history = holder is None
        if holder is None:
            holder = await self._uow.file_versions.holder(kb_id, sha256, other_than)
        if holder is None:
            return
        where = await self._uow.nodes.path(holder.id)
        trashed = holder.deleted_at is not None
        if in_history:
            message = f"já está no histórico de {where}"
        else:
            message = f"está na Lixeira: {where}" if trashed else f"já está em {where}"
        raise Duplicate(message, {"node_id": str(holder.id), "path": where, "trashed": trashed, "history": in_history})

    async def _commit(self, node: NodeRead) -> FileNodeRead:
        detail = FileNodeRead(
            **node.model_dump(),
            path=await self._uow.nodes.path(node.id),
            file=await self._uow.files.of_node(node.id),
            versions=await self._uow.file_versions.count({"node_id": node.id}) + 1,
        )
        await self._uow.commit()
        return detail
