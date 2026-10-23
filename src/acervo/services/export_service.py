import asyncio
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from zipstream import ZipStream

from acervo.core.errors import ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.file import FileLink
from acervo.schemas.node import NodeRead
from acervo.services.file_service import signed_link
from acervo.services.storage import Storage

# Characters no zip reader or file system takes in a name, the path separators among them.
_UNSAFE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def _safe(title: str) -> str:
    name = _UNSAFE.sub("_", title).strip(" .")
    return name or "_"


@dataclass(frozen=True)
class Export:
    """What the export route sends: the zip's name and its bytes as they are made."""

    filename: str
    body: Iterator[bytes]


class ExportService:
    """A page or folder and everything live under it as a zip: pages as their Markdown, files as stored."""

    def __init__(self, uow: UnitOfWork, storage: Storage) -> None:
        self._uow = uow
        self._storage = storage

    async def link(self, node_id: UUID, secret: str, raw_url: str) -> FileLink:
        """`raw_url` signed for the node's export, so it opens without the key for a short while."""
        await self._root(node_id)
        return signed_link(secret, "export", node_id, None, raw_url)

    async def open(self, node_id: UUID) -> Export:
        """The zip of the node's live subtree: a page as `<título>.md` with its children in `<título>/`, a folder as a
        folder, a file under its title. Names are made safe for a zip; equal names among siblings get " (2)", …"""
        root = await self._root(node_id)
        children: dict[UUID | None, list[NodeRead]] = defaultdict(list)
        for node in sorted(await self._uow.nodes.subtree(root.id), key=lambda node: (node.sort, str(node.id))):
            if node.deleted_at is None:
                children[node.parent_id].append(node)
        archive = ZipStream(sized=False)
        name = _safe(root.title)
        await self._add(archive, root, name, children, asyncio.get_running_loop())
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        return Export(f"{name}.zip", iter(archive))

    async def _add(
        self,
        archive: ZipStream,
        node: NodeRead,
        path: str,
        children: dict[UUID | None, list[NodeRead]],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        if node.kind == "file":
            key = (await self._uow.files.of_node(node.id)).storage_key
            archive.add(_blocking(self._storage.stream(key), loop), path)
            return
        if node.kind == "page":
            text = await self._uow.page_drafts.get_by(node_id=node.id)
            markdown = (await self._uow.page_versions.current(node.id)).markdown if text is None else text.markdown
            archive.add(markdown.encode(), f"{path}.md")
        else:
            archive.mkdir(f"{path}/")
        taken: set[str] = set()
        for child in children[node.id]:
            await self._add(archive, child, f"{path}/{_free(child, taken)}", children, loop)

    async def _root(self, node_id: UUID) -> NodeRead:
        node = await self._uow.nodes.live(node_id)
        if node.kind == "file":
            raise ValidationError("só páginas e pastas são exportadas", {"id": str(node_id)})
        return node


def _free(node: NodeRead, taken: set[str]) -> str:
    """The node's safe name, with " (2)", " (3)", … while a sibling already took it; a page takes both `<name>.md`
    and the folder `<name>` of its children, and a file and a folder of one name clash on disk. Compared without
    case, as most file systems do."""
    safe = _safe(node.title)
    suffix = PurePosixPath(safe).suffix if node.kind == "file" else ""
    stem = safe.removesuffix(suffix)
    count, name = 1, safe
    while True:
        folded = name.casefold()
        claims = {f"{folded}.md", folded} if node.kind == "page" else {folded}
        if not claims & taken:
            taken |= claims
            return name
        count += 1
        name = f"{stem} ({count}){suffix}"


def _blocking(body: AsyncIterator[bytes], loop: asyncio.AbstractEventLoop) -> Iterator[bytes]:
    """The stored bytes for the zip, which is made in a worker thread: each chunk is awaited on the event loop.

    A storage error raises here, so the response breaks off instead of ending as a shorter zip.
    """
    while (chunk := asyncio.run_coroutine_threadsafe(_next(body), loop).result()) is not None:
        yield chunk


async def _next(body: AsyncIterator[bytes]) -> bytes | None:
    return await anext(body, None)
