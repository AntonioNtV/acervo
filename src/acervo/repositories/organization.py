from uuid import UUID

from sqlalchemy import delete, func, or_, select

from acervo.db.models.file import File
from acervo.db.models.file_version import FileVersion
from acervo.db.models.kb import Kb
from acervo.db.models.membership import Membership
from acervo.db.models.node import Node
from acervo.db.models.organization import Organization
from acervo.db.models.page_attachment import PageAttachment
from acervo.db.models.page_draft import PageDraft
from acervo.db.models.page_link import PageLink
from acervo.db.models.page_version import PageVersion
from acervo.repositories.base import BaseRepository
from acervo.schemas.organization import OrganizationChange, OrganizationCreate, OrganizationRecord

IMAGE = "image:"


class OrganizationRepository(BaseRepository[Organization, OrganizationRecord, OrganizationCreate, OrganizationChange]):
    orm_model = Organization
    read_schema = OrganizationRecord

    async def create_personal(self, account_id: UUID) -> OrganizationRecord:
        """The account's Pessoal, with the account as its Owner."""
        personal = await self.create(OrganizationCreate(name="Pessoal"), personal_of=account_id)
        self._session.add(Membership(organization_id=personal.id, account_id=account_id, role="owner"))
        await self._flush()
        return personal

    async def delete(self, organization_id: UUID) -> tuple[list[str], list[str], list[str]]:
        """Removes the organization with its bases, every node, version, file version, invite and membership; trashed
        ones too. Returns what the bucket no longer needs: the files' storage keys, and the cover and attachment
        hashes no other base uses. Run while the deleting Owner's membership stands, so its bases are visible."""
        kbs = select(Kb.id).where(Kb.organization_id == organization_id).scalar_subquery()
        nodes = select(Node.id).where(Node.kb_id.in_(kbs)).scalar_subquery()
        keys = await self._session.scalars(
            select(File.storage_key)
            .where(File.node_id.in_(nodes))
            .union(select(FileVersion.storage_key).where(FileVersion.node_id.in_(nodes)))
        )
        file_keys = list(keys)
        covers = list(
            await self._session.scalars(
                select(func.substr(Node.cover, len(IMAGE) + 1))
                .where(Node.id.in_(nodes), Node.cover.startswith(IMAGE))
                .distinct()
            )
        )
        attachments = list(
            await self._session.scalars(
                select(PageAttachment.sha256).where(PageAttachment.page_id.in_(nodes)).distinct()
            )
        )
        await self._session.execute(
            delete(PageLink).where(or_(PageLink.kb_id.in_(kbs), PageLink.from_node_id.in_(nodes)))
        )
        for table in (PageVersion, PageDraft, FileVersion, File):
            await self._session.execute(delete(table).where(table.node_id.in_(nodes)))
        # Attachments, favorites and follows of the nodes go by cascade.
        await self._session.execute(delete(Node).where(Node.kb_id.in_(kbs)))
        await self._session.execute(delete(Kb).where(Kb.organization_id == organization_id))
        # Invites, memberships, base roles and security events go by cascade.
        await self._session.execute(delete(Organization).where(Organization.id == organization_id))
        in_use = set(await self._session.scalars(select(func.acervo.shas_in_use([*covers, *attachments]))))
        return file_keys, [s for s in covers if s not in in_use], [s for s in attachments if s not in in_use]
