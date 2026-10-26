import asyncio
import hashlib
import io
from collections.abc import AsyncIterator
from typing import BinaryIO
from uuid import UUID

from acervo.core.errors import ForbiddenError, LastOwner, NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.organization import (
    MemberRead,
    MembershipCreate,
    MembershipRecord,
    MembershipUpdate,
    OrganizationChange,
    OrganizationCreate,
    OrganizationRead,
    OrganizationRecord,
    OrganizationUpdate,
    OrgRole,
)
from acervo.services.access_service import AccessService
from acervo.services.account_service import _square_png
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.storage import Storage

# The account photo's limit (`Settings.photo_max_bytes`'s default): the logo goes through the same crop.
LOGO_MAX_BYTES = 2 * 1024 * 1024


def logo_key(organization_id: UUID, sha256: str) -> str:
    return f"organization/{organization_id}/{sha256}.png"


class OrganizationService:
    """Organizations and their members: create, rename, logo, roles, remove, leave."""

    def __init__(self, uow: UnitOfWork, storage: Storage, mailer: Mailer, access: AccessService) -> None:
        self._uow = uow
        self._storage = storage
        self._mailer = mailer
        self._access = access

    async def mine(self, account_id: UUID) -> list[OrganizationRead]:
        """Pessoal first, then by name."""
        memberships = await self._uow.memberships.of_account(account_id)
        read = [OrganizationRead.of(await self._uow.organizations.get(m.organization_id), m.role) for m in memberships]
        return sorted(read, key=lambda o: (not o.personal, o.name.casefold()))

    async def create(self, account_id: UUID, data: OrganizationCreate) -> OrganizationRead:
        organization = await self._uow.organizations.create(OrganizationCreate(name=_name(data.name)))
        await self._uow.memberships.create(
            MembershipCreate(organization_id=organization.id, account_id=account_id, role="owner")
        )
        await self._uow.commit()
        return OrganizationRead.of(organization, "owner")

    async def get(self, account_id: UUID, organization_id: UUID) -> OrganizationRead:
        role = await self._access.require_org(account_id, organization_id, "member")
        return OrganizationRead.of(await self._uow.organizations.get(organization_id), role)

    async def update(self, account_id: UUID, organization_id: UUID, data: OrganizationUpdate) -> OrganizationRead:
        role = await self._access.require_org(account_id, organization_id, "admin")
        change = OrganizationChange(**data.model_dump(exclude_none=True))
        if change.name is not None:
            # A Pessoal is never renamed into a team.
            await self._team(organization_id)
            change.name = _name(change.name)
        organization = await self._uow.organizations.update(organization_id, change)
        await self._uow.commit()
        return OrganizationRead.of(organization, role)

    async def set_logo(self, account_id: UUID, organization_id: UUID, source: BinaryIO) -> OrganizationRead:
        """Keeps the centered square of the image as the logo; the previous one leaves the bucket."""
        role = await self._access.require_org(account_id, organization_id, "admin")
        source.seek(0)
        data = source.read(LOGO_MAX_BYTES + 1)
        if len(data) > LOGO_MAX_BYTES:
            raise ValidationError("o logo passa de 2 MB", {"max_bytes": LOGO_MAX_BYTES})
        png = await asyncio.to_thread(_square_png, data)
        key = logo_key(organization_id, hashlib.sha256(png).hexdigest())
        await self._storage.put(key, io.BytesIO(png), len(png))
        return await self._replace_logo(organization_id, key, role)

    async def remove_logo(self, account_id: UUID, organization_id: UUID) -> OrganizationRead:
        role = await self._access.require_org(account_id, organization_id, "admin")
        return await self._replace_logo(organization_id, None, role)

    async def open_logo(self, account_id: UUID, organization_id: UUID) -> tuple[str, AsyncIterator[bytes]]:
        """The logo's key, whose name is its hash, and its bytes."""
        await self._access.require_org(account_id, organization_id, "member")
        organization = await self._uow.organizations.get(organization_id)
        if organization.logo_key is None:
            raise NotFoundError(f"logo of {organization_id} not found", {"id": str(organization_id)})
        # The bytes come from the bucket; the database is not held while they are sent.
        await self._uow.rollback()
        return organization.logo_key, self._storage.stream(organization.logo_key)

    async def members(self, account_id: UUID, organization_id: UUID) -> list[MemberRead]:
        await self._access.require_org(account_id, organization_id, "admin")
        await self._team(organization_id)
        memberships = await self._uow.memberships.of_organization(organization_id)
        read = [MemberRead.of(await self._uow.accounts.get(m.account_id), m.role) for m in memberships]
        return sorted(read, key=lambda m: (m.name.casefold(), m.email.casefold()))

    async def change_role(self, actor_id: UUID, organization_id: UUID, account_id: UUID, role: OrgRole) -> MemberRead:
        """Admins change roles below Owner; Owners change any, but never leave the organization without one."""
        organization, membership = await self._manage(actor_id, organization_id, account_id, role)
        if membership.role == "owner" and role != "owner":
            await self._keep_an_owner(organization_id)
        await self._uow.memberships.update(membership.id, MembershipUpdate(role=role))
        await self._uow.commit()
        account = await self._uow.accounts.get(account_id)
        if role != membership.role:
            actor = await self._uow.accounts.get(actor_id)
            values = {
                "actor": actor.name,
                "organization": organization.name,
                "role": role,
                "old_role": membership.role,
                # The organization is not in the URL; the rail switches to it from the bases.
                "link": "/bases",
            }
            await self._mailer.send(account.email, MailTemplate.ROLE_CHANGED, account.language, values)
        return MemberRead.of(account, role)

    async def remove(self, actor_id: UUID, organization_id: UUID, account_id: UUID) -> None:
        """Takes the member out, with their roles on the organization's bases; they are told by email."""
        organization, membership = await self._manage(actor_id, organization_id, account_id, None)
        await self._drop(membership)
        account, actor = await self._uow.accounts.get(account_id), await self._uow.accounts.get(actor_id)
        values = {"actor": actor.name, "organization": organization.name}
        await self._mailer.send(account.email, MailTemplate.REMOVED, account.language, values)

    async def leave(self, account_id: UUID, organization_id: UUID) -> None:
        await self._access.require_org(account_id, organization_id, "member")
        await self._team(organization_id)
        membership = await self._uow.memberships.get_by(organization_id=organization_id, account_id=account_id)
        assert membership is not None
        await self._drop(membership)

    async def _team(self, organization_id: UUID) -> OrganizationRecord:
        """The organization, unless it is a Pessoal: an organization of one, without members to manage."""
        organization = await self._uow.organizations.get(organization_id)
        if organization.personal_of is not None:
            raise ForbiddenError("a Pessoal has no members", {"organization_id": str(organization_id)})
        return organization

    async def _manage(
        self, actor_id: UUID, organization_id: UUID, account_id: UUID, new_role: OrgRole | None
    ) -> tuple[OrganizationRecord, MembershipRecord]:
        """The organization and the member an Owner or Admin acts on; an Admin neither touches nor makes Owners."""
        actor_role = await self._access.require_org(actor_id, organization_id, "admin")
        organization = await self._team(organization_id)
        membership = await self._uow.memberships.get_by(organization_id=organization_id, account_id=account_id)
        if membership is None:
            raise NotFoundError(f"member {account_id} not found", {"account_id": str(account_id)})
        if actor_role != "owner" and "owner" in (membership.role, new_role):
            raise ForbiddenError("only an Owner manages Owners", {"organization_id": str(organization_id)})
        return organization, membership

    async def _keep_an_owner(self, organization_id: UUID) -> None:
        # shortcut: two Owners demoting each other at the same instant can both pass; lock the rows if that shows up.
        if await self._uow.memberships.count({"organization_id": organization_id, "role": "owner"}) <= 1:
            raise LastOwner("the organization needs an Owner", {"organization_id": str(organization_id)})

    async def _drop(self, membership: MembershipRecord) -> None:
        if membership.role == "owner":
            await self._keep_an_owner(membership.organization_id)
        await self._uow.memberships.delete(membership.id)
        # Someone out of the organization loses its bases at once, even those they were added to.
        await self._uow.base_members.delete_in_organization(membership.account_id, membership.organization_id)
        await self._uow.commit()

    async def _replace_logo(self, organization_id: UUID, key: str | None, role: OrgRole) -> OrganizationRead:
        old = (await self._uow.organizations.get(organization_id)).logo_key
        organization = await self._uow.organizations.update(organization_id, OrganizationChange(logo_key=key))
        await self._uow.commit()
        # Only after the commit, so the organization never points at a deleted logo.
        if old is not None and old != key:
            await self._storage.delete(old)
        return OrganizationRead.of(organization, role)


def _name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise ValidationError("a organização precisa de um nome", {"name": name})
    return stripped
