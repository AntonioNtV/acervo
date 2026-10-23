from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.repositories.agent import AgentRepository
from acervo.repositories.conversation import ConversationRepository
from acervo.repositories.decision_log import DecisionLogRepository
from acervo.repositories.favorite import FavoriteRepository
from acervo.repositories.file import FileRepository
from acervo.repositories.file_version import FileVersionRepository
from acervo.repositories.kb import KbRepository
from acervo.repositories.message import MessageRepository
from acervo.repositories.node import NodeRepository
from acervo.repositories.page_draft import PageDraftRepository
from acervo.repositories.page_link import PageLinkRepository
from acervo.repositories.page_version import PageVersionRepository
from acervo.repositories.proposal import ProposalRepository


class UnitOfWork:
    """One session and its repositories; the caller commits, an exception rolls back."""

    kbs: KbRepository
    nodes: NodeRepository
    files: FileRepository
    file_versions: FileVersionRepository
    page_versions: PageVersionRepository
    page_drafts: PageDraftRepository
    page_links: PageLinkRepository
    favorites: FavoriteRepository
    agents: AgentRepository
    conversations: ConversationRepository
    messages: MessageRepository
    proposals: ProposalRepository
    decisions: DecisionLogRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.kbs = KbRepository(self._session)
        self.nodes = NodeRepository(self._session)
        self.files = FileRepository(self._session)
        self.file_versions = FileVersionRepository(self._session)
        self.page_versions = PageVersionRepository(self._session)
        self.page_drafts = PageDraftRepository(self._session)
        self.page_links = PageLinkRepository(self._session)
        self.favorites = FavoriteRepository(self._session)
        self.agents = AgentRepository(self._session)
        self.conversations = ConversationRepository(self._session)
        self.messages = MessageRepository(self._session)
        self.proposals = ProposalRepository(self._session)
        self.decisions = DecisionLogRepository(self._session)
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
