import asyncio
import hashlib
import mimetypes
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import ConflictError
from acervo.pdfs import reader
from acervo.pdfs.storage import Storage, key_for
from acervo.store.models import File, FileVersion, Node
from acervo.store.repositories import key_between, last_sort, live_folder, lock_kb, path, sibling_title_taken

CHUNK_SIZE = 1024 * 1024
PDF = "application/pdf"


@dataclass(frozen=True)
class Upload:
    """An uploaded file, hashed where it is, with what is known about it."""

    source: BinaryIO
    sha256: str
    size: int
    mime: str
    pages: int | None
    protected: bool

    def columns(self, kb_id: uuid.UUID) -> dict[str, Any]:
        return {
            "storage_key": key_for(kb_id, self.sha256),
            "sha256": self.sha256,
            "size": self.size,
            "mime": self.mime,
            "pages": self.pages,
            "protected": self.protected,
            # Known only once F2 reads the new content; never carried over from a replaced one.
            "doc_type": None,
            "sensitive": False,
            "map": None,
            "map_origin": None,
        }


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


async def stage(source: BinaryIO, filename: str) -> Upload:
    """Reads `source` in chunks, never whole in memory, and leaves it at its start."""
    sha256, size, head = await asyncio.to_thread(_hash, source)
    if head == b"%PDF":
        meta = await asyncio.to_thread(_pdf_metadata, source)
        mime, pages, protected = PDF, meta.pages, meta.protected
    else:
        guessed = mimetypes.guess_type(filename)[0]
        mime = guessed if guessed and guessed != PDF else "application/octet-stream"
        pages, protected = None, False
    return Upload(source, sha256, size, mime, pages, protected)


async def refuse_duplicate(
    session: AsyncSession, kb_id: uuid.UUID, sha256: str, other_than: uuid.UUID | None = None
) -> None:
    """Refuses content the base already holds: in a file, in the trash, or in any file's history."""
    of_base = [Node.kb_id == kb_id, *([Node.id != other_than] if other_than else [])]
    holder = await session.scalar(
        select(Node).join(File, File.node_id == Node.id).where(*of_base, File.sha256 == sha256).limit(1)
    )
    in_history = holder is None
    if in_history:
        holder = await session.scalar(
            select(Node)
            .join(FileVersion, FileVersion.node_id == Node.id)
            .where(*of_base, FileVersion.sha256 == sha256)
            .limit(1)
        )
    if holder is None:
        return
    where = await path(session, holder.id)
    trashed = holder.deleted_at is not None
    if in_history:
        message = f"já está no histórico de {where}"
    else:
        message = f"está na Lixeira: {where}" if trashed else f"já está em {where}"
    raise ConflictError(message, {"node_id": str(holder.id), "path": where, "trashed": trashed})


async def save(
    session: AsyncSession,
    storage: Storage,
    kb_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    filename: str,
    source: BinaryIO,
) -> File:
    """Stores a file byte for byte into a folder of the base, as the last of its siblings."""
    upload = await stage(source, filename)
    await lock_kb(session, kb_id)
    await live_folder(session, kb_id, parent_id)
    await refuse_duplicate(session, kb_id, upload.sha256)
    if await sibling_title_taken(session, kb_id, parent_id, "file", filename):
        raise ConflictError("já existe", {"title": filename})
    await storage.put(key_for(kb_id, upload.sha256), upload.source, upload.size)
    node = Node(
        id=uuid.uuid4(),
        kb_id=kb_id,
        parent_id=parent_id,
        kind="file",
        title=filename,
        sort=key_between(await last_sort(session, kb_id, parent_id), None),
    )
    session.add(node)
    await session.flush()
    file = File(node_id=node.id, **upload.columns(kb_id))
    session.add(file)
    await session.flush()
    return file
