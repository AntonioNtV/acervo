import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID

from acervo.core.errors import NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.file import FileLink
from acervo.schemas.node import NodeRead, NodeUpdate
from acervo.services.file_service import read_hash, signed_link
from acervo.services.storage import Storage

IMAGE = "image:"


def cover_key(sha256: str) -> str:
    """Outside `kb/`, where the tree's files live: a cover is not a file of the tree. Not under the base either, so
    the cover stays reachable when its node moves to another base."""
    return f"covers/{sha256}"


def _mime(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


@dataclass(frozen=True)
class CoverImage:
    """What the raw route sends: the image's media type and its bytes."""

    media_type: str
    body: AsyncIterator[bytes]


class CoverService:
    """Uploaded cover images of folders and pages, kept in the bucket by content and opened by signed link."""

    def __init__(self, uow: UnitOfWork, storage: Storage, max_bytes: int) -> None:
        self._uow = uow
        self._storage = storage
        self._max_bytes = max_bytes

    async def upload(self, node_id: UUID, source: BinaryIO) -> NodeRead:
        """Stores a PNG, JPEG or WebP and makes it the node's cover; the old image stays, another node may share it."""
        node = await self._uow.nodes.live(node_id)
        if node.kind == "file":
            raise ValidationError("um arquivo não tem capa", {"node_id": str(node_id)})
        sha256, size, head = await asyncio.to_thread(read_hash, source, self._max_bytes)
        if _mime(head) is None:
            raise ValidationError("a capa deve ser uma imagem PNG, JPEG ou WebP", {"node_id": str(node_id)})
        if size > self._max_bytes:
            limit = self._max_bytes // (1024 * 1024)
            raise ValidationError(f"a capa passa de {limit} MB", {"max_bytes": self._max_bytes})
        await self._storage.put(cover_key(sha256), source, size)
        node = await self._uow.nodes.update(node_id, NodeUpdate(cover=f"{IMAGE}{sha256}"))
        await self._uow.commit()
        return node

    async def link(self, node_id: UUID, secret: str, session_id: UUID, raw_url: str) -> FileLink:
        """`raw_url` signed for the node's cover, so it opens without the cookie for a short while."""
        await self._image_key(node_id)
        return signed_link(secret, "cover", node_id, None, session_id, raw_url)

    async def open(self, node_id: UUID) -> CoverImage:
        """The node's cover image with the media type read from its first bytes."""
        key = await self._image_key(node_id)
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        body = self._storage.stream(key)
        first = await anext(body, b"")
        return CoverImage(_mime(first) or "application/octet-stream", _prepend(first, body))

    async def _image_key(self, node_id: UUID) -> str:
        node = await self._uow.nodes.live(node_id)
        if not node.cover or not node.cover.startswith(IMAGE):
            raise NotFoundError(f"cover of {node_id} not found", {"id": str(node_id)})
        return cover_key(node.cover.removeprefix(IMAGE))


async def _prepend(first: bytes, rest: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    yield first
    async for chunk in rest:
        yield chunk
