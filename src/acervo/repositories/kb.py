from collections.abc import Collection
from uuid import UUID

from sqlalchemy import delete, func, select, union_all

from acervo.core.errors import NotFoundError
from acervo.db.models.account import Account
from acervo.db.models.base_member import BaseMember
from acervo.db.models.file_version import FileVersion
from acervo.db.models.kb import Kb
from acervo.db.models.node import Node
from acervo.db.models.page_version import PageVersion
from acervo.repositories.base import BaseRepository
from acervo.repositories.node import contains
from acervo.schemas.account import AccountRecord
from acervo.schemas.kb import KbCreate, KbRead, KbSummary, KbUpdate
from acervo.schemas.organization import BaseMemberRecord, GeneralAccess, MemberRead


class KbRepository(BaseRepository[Kb, KbRead, KbCreate, KbUpdate]):
    orm_model = Kb
    read_schema = KbRead

    async def lock(self, kb_id: UUID) -> None:
        """One writer per base until the transaction ends, so checks such as "já existe" hold until the write."""
        await self._session.execute(select(func.pg_advisory_xact_lock(int.from_bytes(kb_id.bytes[:8], signed=True))))

    async def get_in(self, kb_id: UUID, *, trashed: bool = False) -> KbRead:
        """The base, live or in the trash as asked; any other is not found."""
        kb = await self._session.get(Kb, kb_id, populate_existing=True)
        if kb is None or (kb.deleted_at is not None) != trashed:
            raise NotFoundError(f"kb {kb_id} not found", {"id": str(kb_id)})
        return self._to_read(kb)

    async def summaries(self, ids: Collection[UUID], name: str = "") -> list[KbSummary]:
        """The live bases of `ids` with their live counts, most recently edited first."""
        counts = (
            select(
                Node.kb_id,
                func.count().filter(Node.kind == "page").label("pages"),
                func.count().filter(Node.kind == "file").label("files"),
            )
            .where(Node.deleted_at.is_(None))
            .group_by(Node.kb_id)
            .subquery()
        )
        edits = union_all(
            select(Kb.id.label("kb_id"), Kb.updated_at),
            select(Node.kb_id, Node.updated_at),
            select(Node.kb_id, PageVersion.updated_at).join(Node, Node.id == PageVersion.node_id),
            select(Node.kb_id, FileVersion.updated_at).join(Node, Node.id == FileVersion.node_id),
        ).subquery()
        last_edits = select(edits.c.kb_id, func.max(edits.c.updated_at).label("at")).group_by(edits.c.kb_id).subquery()
        query = (
            select(Kb, func.coalesce(counts.c.pages, 0), func.coalesce(counts.c.files, 0), last_edits.c.at)
            .outerjoin(counts, counts.c.kb_id == Kb.id)
            .join(last_edits, last_edits.c.kb_id == Kb.id)
            .where(Kb.deleted_at.is_(None), Kb.id.in_(ids))
            .order_by(last_edits.c.at.desc(), Kb.name)
        )
        if name.strip():
            query = query.where(contains(Kb.name, name.strip()))
        rows = await self._session.execute(query.execution_options(populate_existing=True))
        return [
            KbSummary(**self._to_read(kb).model_dump(), pages=pages, files=files, last_edit=last_edit)
            for kb, pages, files, last_edit in rows
        ]

    async def trashed(self, ids: Collection[UUID]) -> list[KbRead]:
        """The bases of `ids` in the trash, most recently trashed first."""
        query = select(Kb).where(Kb.deleted_at.is_not(None), Kb.id.in_(ids)).order_by(Kb.deleted_at.desc())
        return [
            self._to_read(kb) for kb in await self._session.scalars(query.execution_options(populate_existing=True))
        ]

    async def set_general_access(self, kb_id: UUID, general_access: GeneralAccess) -> None:
        kb = await self._get_orm(kb_id)
        kb.general_access = general_access
        await self._flush()

    async def members(self, kb_id: UUID) -> list[MemberRead]:
        """The people added to the base with their base role, by name."""
        query = (
            select(Account, BaseMember)
            .join(BaseMember, BaseMember.account_id == Account.id)
            .where(BaseMember.kb_id == kb_id)
            .order_by(Account.name, Account.email)
        )
        return [
            MemberRead.of(AccountRecord.model_validate(account), BaseMemberRecord.model_validate(added).role)
            for account, added in await self._session.execute(query)
        ]

    async def remove_member(self, kb_id: UUID, account_id: UUID) -> None:
        await self._session.execute(
            delete(BaseMember).where(BaseMember.kb_id == kb_id, BaseMember.account_id == account_id)
        )
