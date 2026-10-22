from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.repositories.file import FileRepository
from acervo.repositories.file_version import FileVersionRepository
from acervo.repositories.kb import KbRepository
from acervo.repositories.node import NodeRepository


class UnitOfWork:
    """One session and its repositories; the caller commits, an exception rolls back."""

    kbs: KbRepository
    nodes: NodeRepository
    files: FileRepository
    file_versions: FileVersionRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.kbs = KbRepository(self._session)
        self.nodes = NodeRepository(self._session)
        self.files = FileRepository(self._session)
        self.file_versions = FileVersionRepository(self._session)
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
