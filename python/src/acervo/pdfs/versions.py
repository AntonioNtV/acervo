import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import ConflictError, NotFoundError
from acervo.pdfs.files import staged
from acervo.pdfs.storage import Storage, key_for
from acervo.store.models import File, FileColumns, FileVersion, Node
from acervo.store.repositories import get

_COLUMNS = tuple(FileColumns.__annotations__)


async def current(session: AsyncSession, node_id: uuid.UUID) -> File:
    file = await session.scalar(select(File).where(File.node_id == node_id))
    if file is None:
        raise NotFoundError(f"file of node {node_id} not found")
    return file


def _to_history(session: AsyncSession, file: File) -> None:
    session.add(
        FileVersion(
            node_id=file.node_id,
            replaced_at=datetime.now(UTC),
            **{column: getattr(file, column) for column in _COLUMNS},
        )
    )


def _take(file: File, columns: dict[str, Any]) -> None:
    for column in _COLUMNS:
        setattr(file, column, columns[column])


async def replace(session: AsyncSession, storage: Storage, node_id: uuid.UUID, source: BinaryIO) -> File:
    """The file node gets new content; the current one goes to its history."""
    file = await current(session, node_id)
    node = await get(session, Node, node_id)
    async with staged(source, node.title) as upload:
        if upload.sha256 == file.sha256:
            raise ConflictError("é o mesmo arquivo")
        await storage.put(key_for(node.kb_id, upload.sha256), upload.path)
    _to_history(session, file)
    _take(file, upload.columns(node.kb_id))
    await session.flush()
    return file


async def list_versions(session: AsyncSession, node_id: uuid.UUID) -> list[FileVersion]:
    """The file's history, newest first; the current content is not in it."""
    query = select(FileVersion).where(FileVersion.node_id == node_id).order_by(FileVersion.replaced_at.desc())
    return list(await session.scalars(query))


async def _version(session: AsyncSession, node_id: uuid.UUID, version_id: uuid.UUID) -> FileVersion:
    version = await get(session, FileVersion, version_id)
    if version.node_id != node_id:
        raise NotFoundError(f"file_version {version_id} not found")
    return version


async def restore(session: AsyncSession, node_id: uuid.UUID, version_id: uuid.UUID) -> File:
    """An old version becomes current again; the current one goes to history and no version is removed."""
    version = await _version(session, node_id, version_id)
    file = await current(session, node_id)
    if version.sha256 == file.sha256:
        raise ConflictError("é o mesmo arquivo")
    _to_history(session, file)
    _take(file, {column: getattr(version, column) for column in _COLUMNS})
    await session.flush()
    return file


async def open_bytes(
    session: AsyncSession, storage: Storage, node_id: uuid.UUID, version_id: uuid.UUID | None = None
) -> tuple[File | FileVersion, AsyncIterator[bytes]]:
    """The metadata and a stream of the bytes of the current content, or of one version of it."""
    row = await current(session, node_id) if version_id is None else await _version(session, node_id, version_id)
    return row, storage.stream(row.storage_key)
