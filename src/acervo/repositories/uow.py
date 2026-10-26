from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction

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
from acervo.repositories.passkey import PasskeyRepository
from acervo.repositories.password_reset import PasswordResetRepository
from acervo.repositories.pending_sign_in import PendingSignInRepository
from acervo.repositories.security_event import SecurityEventRepository
from acervo.repositories.session import SessionRepository

APP_ROLE = "acervo_app"


def _set_account(session: Session, connection: Connection) -> None:
    account_id = session.info.get("account_id")
    connection.execute(text("select set_config('app.account_id', :id, true)"), {"id": str(account_id or "")})
    session.info["account_in_transaction"] = account_id


def _as_app(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    # Local to the transaction: it ends with it, so a connection goes back to the pool as its owner.
    connection.exec_driver_sql(f"set local role {APP_ROLE}")
    _set_account(session, connection)


def _catch_up(session: Session) -> None:
    """`act_as` may come after the transaction began (the request resolves its cookie first)."""
    if session.in_transaction() and session.info.get("account_in_transaction") != session.info.get("account_id"):
        _set_account(session, session.connection())


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
    passkeys: PasskeyRepository
    pending_sign_ins: PendingSignInRepository
    security_events: SecurityEventRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        # Every transaction runs under the role row-level security binds, seeing only the bases of `act_as`.
        sync = self._session.sync_session
        event.listen(sync, "after_begin", _as_app)
        event.listen(sync, "do_orm_execute", lambda state: _catch_up(state.session))
        event.listen(sync, "before_flush", lambda session, *_: _catch_up(session))
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
        self.passkeys = PasskeyRepository(self._session)
        self.pending_sign_ins = PendingSignInRepository(self._session)
        self.security_events = SecurityEventRepository(self._session)
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
        """Reads that depend on who asks (a node's `favorite`), and the bases row-level security lets through,
        answer for this account from now on."""
        self._session.info["account_id"] = account_id

    @property
    def account_id(self) -> UUID | None:
        """The account `act_as` named; None outside a signed-in request."""
        account_id: UUID | None = self._session.info.get("account_id")
        return account_id
