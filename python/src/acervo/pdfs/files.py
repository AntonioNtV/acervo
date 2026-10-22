import asyncio
import hashlib
import mimetypes
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from acervo.errors import ConflictError, ValidationError
from acervo.pdfs import reader
from acervo.pdfs.storage import Storage, key_for
from acervo.store.models import File, Node
from acervo.store.repositories import get, sibling_title_taken

CHUNK_SIZE = 1024 * 1024
PDF = "application/pdf"
# The ASCII order of these is the order of `collate "C"`, so the next one always sorts after.
_SORT_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True)
class Upload:
    """A file copied to a local path while it was hashed, with what is known about it."""

    path: Path
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


def _copy_and_hash(source: BinaryIO, path: Path) -> tuple[str, int, bytes]:
    digest = hashlib.sha256()
    size = 0
    head = b""
    with path.open("wb") as target:
        while chunk := source.read(CHUNK_SIZE):
            if size == 0:
                head = chunk[:4]
            digest.update(chunk)
            target.write(chunk)
            size += len(chunk)
    return digest.hexdigest(), size, head


@asynccontextmanager
async def staged(source: BinaryIO, filename: str) -> AsyncIterator[Upload]:
    """Reads `source` in chunks into a temporary file, never whole in memory; the file is gone on exit."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "upload"
        sha256, size, head = await asyncio.to_thread(_copy_and_hash, source, path)
        if head == b"%PDF":
            meta = await asyncio.to_thread(reader.metadata, path)
            mime, pages, protected = PDF, meta.pages, meta.protected
        else:
            guessed = mimetypes.guess_type(filename)[0]
            mime = guessed if guessed and guessed != PDF else "application/octet-stream"
            pages, protected = None, False
        yield Upload(path, sha256, size, mime, pages, protected)


async def node_path(session: AsyncSession, node: Node) -> str:
    titles = [node.title]
    while node.parent_id is not None:
        node = await get(session, Node, node.parent_id)
        titles.append(node.title)
    return "/".join(reversed(titles))


async def _sort_after_last(session: AsyncSession, kb_id: uuid.UUID, parent_id: uuid.UUID | None) -> str:
    parent = Node.parent_id.is_(None) if parent_id is None else Node.parent_id == parent_id
    last = await session.scalar(select(func.max(Node.sort.collate("C"))).where(Node.kb_id == kb_id, parent))
    if last is None:
        return "a0"
    position = _SORT_DIGITS.find(last[-1])
    if 0 <= position < len(_SORT_DIGITS) - 1:
        return last[:-1] + _SORT_DIGITS[position + 1]
    return last + "V"


async def save(
    session: AsyncSession,
    storage: Storage,
    kb_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    filename: str,
    source: BinaryIO,
) -> File:
    """Stores a file byte for byte into a folder of the base, as the last of its siblings."""
    if parent_id is not None:
        parent = await get(session, Node, parent_id)
        if parent.kb_id != kb_id or parent.kind != "folder" or parent.deleted_at is not None:
            raise ValidationError("a pasta não está nesta base")
    async with staged(source, filename) as upload:
        duplicate = await session.scalar(
            select(Node).join(File, File.node_id == Node.id).where(Node.kb_id == kb_id, File.sha256 == upload.sha256)
        )
        if duplicate is not None:
            path = await node_path(session, duplicate)
            trashed = duplicate.deleted_at is not None
            message = f"está na Lixeira: {path}" if trashed else f"já está em {path}"
            raise ConflictError(message, {"node_id": str(duplicate.id), "path": path, "trashed": trashed})
        if await sibling_title_taken(session, kb_id, parent_id, "file", filename):
            raise ConflictError("já existe", {"title": filename})
        await storage.put(key_for(kb_id, upload.sha256), upload.path)
        node = Node(
            id=uuid.uuid4(),
            kb_id=kb_id,
            parent_id=parent_id,
            kind="file",
            title=filename,
            sort=await _sort_after_last(session, kb_id, parent_id),
        )
        session.add(node)
        await session.flush()
        file = File(node_id=node.id, **upload.columns(kb_id))
        session.add(file)
        await session.flush()
        return file
