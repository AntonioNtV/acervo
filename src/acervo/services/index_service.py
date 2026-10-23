"""The search index of each PDF and page, built in the worker (spec index-retrieval §1, skill `pdf-files`)."""

import asyncio
import logging
from uuid import UUID

from acervo.core.settings import RetrievalLimits
from acervo.domain.index import DocIndex
from acervo.pipeline.index.markdown import index_markdown
from acervo.pipeline.index.pdf import index_pdf
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.node import NodeRead
from acervo.services.storage import Storage

INDEX_NODE = "index_node"
FAILED = "não foi possível indexar"
PDF = "application/pdf"

logger = logging.getLogger(__name__)


async def current_key(uow: UnitOfWork, node: NodeRead) -> str | None:
    """What an index of the node is of: a PDF's sha256 or a page's newest version; None for anything else."""
    if node.kind == "page":
        return str((await uow.page_versions.current(node.id)).id)
    if node.kind == "file":
        content = await uow.files.of_node(node.id)
        return content.sha256 if content.mime == PDF else None
    return None


async def request(uow: UnitOfWork, node: NodeRead) -> None:
    """Asks for the node's current version to be indexed, in the caller's transaction; the worker's sweep builds
    it once committed, so a rollback asks for nothing."""
    key = await current_key(uow, node)
    if key is not None:
        await uow.indexes.start(node.id, key)


class IndexService:
    def __init__(self, uow: UnitOfWork, storage: Storage, limits: RetrievalLimits) -> None:
        self._uow = uow
        self._storage = storage
        self._limits = limits

    async def build(self, node_id: UUID, key: str) -> None:
        """Indexes version `key` of the node; the previous index stays readable until this one is ready."""
        node = await self._uow.nodes.get(node_id)
        current = await current_key(self._uow, node)
        if current != key:
            # The build asked for is no longer the node's content: ask for the current one instead.
            if current is not None:
                await self._uow.indexes.start(node.id, current)
            else:
                await self._uow.indexes.fail(node.id, key, FAILED)
            await self._uow.commit()
            return
        storage_key = (await self._uow.files.of_node(node.id)).storage_key if node.kind == "file" else None
        markdown = (await self._uow.page_versions.current(node.id)).markdown if node.kind == "page" else ""
        # The database is not held while a long PDF is read.
        await self._uow.rollback()
        try:
            index = await self._index(storage_key, markdown)
        except Exception:
            logger.exception("index of node %s at %s failed", node.id, key)
            await self._uow.indexes.fail(node.id, key, FAILED)
        else:
            await self._uow.indexes.finish(node.id, key, index)
        await self._uow.commit()

    async def _index(self, storage_key: str | None, markdown: str) -> DocIndex:
        if storage_key is None:
            return index_markdown(markdown, self._limits)
        async with self._storage.download(storage_key) as path:
            return await asyncio.to_thread(index_pdf, path, self._limits)
