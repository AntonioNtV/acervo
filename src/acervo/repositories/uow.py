from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from acervo.repositories.account import AccountRepository
from acervo.repositories.base_member import BaseMemberRepository
from acervo.repositories.email_code import EmailCodeRepository
from acervo.repositories.favorite import FavoriteRepository
from acervo.repositories.file import FileRepository
from acervo.repositories.file_version import FileVersionRepository
from acervo.repositories.invite import InviteRepository
from acervo.repositories.kb import KbRepository
from acervo.repositories.login_failure import LoginFailureRepository
from acervo.repositories.membership import MembershipRepository
from acervo.repositories.node import NodeRepository
from acervo.repositories.organization import OrganizationRepository
from acervo.repositories.page_attachment import PageAttachmentRepository
from acervo.repositories.page_draft import PageDraftRepository
from acervo.repositories.page_link import PageLinkRepository
from acervo.repositories.page_version import PageVersionRepository
from acervo.repositories.password_reset import PasswordResetRepository
from acervo.repositories.session import SessionRepository


class UnitOfWork:
    """One session and its repositories; the caller commits, an exception rolls back."""

    kbs: KbRepository
    nodes: NodeRepository
    files: FileRepository
    file_versions: FileVersionRepository
    page_versions: PageVersionRepository
    page_drafts: PageDraftRepository
    page_links: PageLinkRepository
    page_attachments: PageAttachmentRepository
    favorites: FavoriteRepository
    accounts: AccountRepository
    sessions: SessionRepository
    email_codes: EmailCodeRepository
    password_resets: PasswordResetRepository
    login_failures: LoginFailureRepository
    organizations: OrganizationRepository
    memberships: MembershipRepository
    base_members: BaseMemberRepository
    invites: InviteRepository

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
        self.page_attachments = PageAttachmentRepository(self._session)
        self.favorites = FavoriteRepository(self._session)
        self.accounts = AccountRepository(self._session)
        self.sessions = SessionRepository(self._session)
        self.email_codes = EmailCodeRepository(self._session)
        self.password_resets = PasswordResetRepository(self._session)
        self.login_failures = LoginFailureRepository(self._session)
        self.organizations = OrganizationRepository(self._session)
        self.memberships = MembershipRepository(self._session)
        self.base_members = BaseMemberRepository(self._session)
        self.invites = InviteRepository(self._session)
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

    def act_as(self, account_id: UUID) -> None:
        """Reads that depend on who asks (a node's `favorite`) answer for this account from now on."""
        self._session.info["account_id"] = account_id

    @property
    def account_id(self) -> UUID | None:
        """The account `act_as` named; None outside a signed-in request."""
        account_id: UUID | None = self._session.info.get("account_id")
        return account_id
