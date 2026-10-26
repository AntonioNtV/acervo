import asyncio
import mimetypes
import re
import unicodedata
from pathlib import PurePosixPath
from typing import BinaryIO
from urllib.parse import quote
from uuid import UUID

from acervo.core.errors import NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.attachment import Attachment, AttachmentCreate, AttachmentRead
from acervo.schemas.file import FileLink
from acervo.schemas.node import NodeRead
from acervo.services.file_service import PDF, Download, read_hash, signed_link
from acervo.services.storage import Storage

_RANGE = re.compile(r"bytes=(\d*)-(\d*)")
# Anything but letters, digits, `.`, `_` and `-` would need escaping in `arquivos/<name>` of the Markdown.
_UNSAFE = re.compile(r"[^\w.-]+")


class AttachmentTooLarge(ValidationError):
    code = "attachment_too_large"


def attachment_key(sha256: str) -> str:
    """Outside `kb/`, like covers: an attachment is not a file of the tree, and it stays reachable when its page moves
    to another base."""
    return f"attachments/{sha256}"


def safe_name(filename: str | None) -> str:
    """The uploaded name without folders, its unsafe characters turned into `-`."""
    base = PurePosixPath((filename or "").replace("\\", "/")).name
    return _UNSAFE.sub("-", unicodedata.normalize("NFC", base)).strip("-.") or "arquivo"


def _mime(head: bytes, name: str) -> str:
    if head.startswith(b"%PDF"):
        return PDF
    guessed = mimetypes.guess_type(name)[0]
    return guessed if guessed and guessed != PDF else "application/octet-stream"


class AttachmentService:
    """Files put in a page: kept by content in the bucket while the page exists, reached through the live page, so
    they follow it to the trash and back and across a move."""

    def __init__(self, uow: UnitOfWork, storage: Storage, max_bytes: int) -> None:
        self._uow = uow
        self._storage = storage
        self._max_bytes = max_bytes

    async def upload(self, page_id: UUID, filename: str | None, source: BinaryIO) -> Attachment:
        """Stores any file byte for byte under a name free in the page: `foto.jpg`, then `foto-2.jpg`, …"""
        page = await self._page(page_id)
        sha256, size, head = await asyncio.to_thread(read_hash, source, self._max_bytes)
        if size > self._max_bytes:
            limit = self._max_bytes // (1024 * 1024)
            raise AttachmentTooLarge(f"o arquivo passa de {limit} MB", {"max_bytes": self._max_bytes})
        await self._uow.kbs.lock(page.kb_id)
        name = await self._free_name(page_id, safe_name(filename))
        await self._storage.put(attachment_key(sha256), source, size)
        attachment = await self._uow.page_attachments.create(
            AttachmentCreate(page_id=page_id, name=name, sha256=sha256, mime=_mime(head, name), size=size)
        )
        await self._uow.commit()
        return Attachment.model_validate(attachment)

    async def link(self, page_id: UUID, name: str, secret: str, raw_url: str) -> FileLink:
        """`raw_url` signed for this attachment, so it opens without the key for a short while."""
        attachment = await self._attachment(page_id, name)
        return signed_link(secret, "attachment", page_id, attachment.id, raw_url)

    async def download(self, page_id: UUID, name: str, signed_id: UUID | None, range_header: str | None) -> Download:
        """The attachment byte for byte, or the one `Range` of bytes asked for (seeking in a video or audio)."""
        attachment = await self._attachment(page_id, name)
        # A link is signed for one attachment's id; another name in its path must not open with it.
        if signed_id is not None and signed_id != attachment.id:
            raise NotFoundError(f"attachment {name} not found", {"name": name})
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        key, size = attachment_key(attachment.sha256), attachment.size
        headers = {
            "Accept-Ranges": "bytes",
            # The type comes from the uploaded name; the browser must not guess another one, such as HTML.
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.name)}",
            "ETag": f'"{attachment.sha256}"',
            # Every link is a new URL and the bytes under a key never change, so the browser may keep them.
            "Cache-Control": "private, max-age=31536000, immutable",
        }
        # As FileService.download: a malformed or multi-part Range is ignored and the whole file is served.
        match = _RANGE.fullmatch(range_header.strip()) if range_header else None
        if match is None or match.groups() == ("", ""):
            headers["Content-Length"] = str(size)
            return Download(200, headers, attachment.mime, self._storage.stream(key))
        first, last = match.groups()
        if first:
            start, end = int(first), min(int(last), size - 1) if last else size - 1
        else:
            start, end = max(size - int(last), 0), size - 1
        if start > end:
            return Download(416, {"Content-Range": f"bytes */{size}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
        return Download(206, headers, attachment.mime, self._storage.stream(key, (start, end)))

    async def _page(self, page_id: UUID) -> NodeRead:
        node = await self._uow.nodes.live(page_id)
        if node.kind != "page":
            raise ValidationError(f"node {page_id} is not a page", {"id": str(page_id)})
        return node

    async def _attachment(self, page_id: UUID, name: str) -> AttachmentRead:
        await self._page(page_id)
        attachment = await self._uow.page_attachments.get_by(page_id=page_id, name=name)
        if attachment is None:
            raise NotFoundError(f"attachment {name} not found", {"name": name})
        return attachment

    async def _free_name(self, page_id: UUID, name: str) -> str:
        path = PurePosixPath(name)
        stem, suffix = path.stem, path.suffix
        candidate, count = name, 1
        while await self._uow.page_attachments.get_by(page_id=page_id, name=candidate):
            count += 1
            candidate = f"{stem}-{count}{suffix}"
        return candidate
