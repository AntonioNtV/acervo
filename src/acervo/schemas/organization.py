from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from acervo.schemas.account import AccountRead, AccountRecord

OrgRole = Literal["owner", "admin", "member"]
BaseRole = Literal["reader", "editor", "admin"]
GeneralAccess = Literal["none", "reader", "editor"]


class OrganizationCreate(BaseModel):
    """An organization to create; its creator becomes its Owner."""

    name: str = Field(min_length=1, description="Name of the organization.")


class OrganizationUpdate(BaseModel):
    """A change to an organization; omitted fields keep their value."""

    name: str | None = Field(default=None, min_length=1, description="New name; cannot be blank.")
    new_base_access: GeneralAccess | None = Field(
        default=None, description="The general access a new base starts with (Acesso de bases novas)."
    )
    require_two_factor: bool | None = Field(
        default=None, description="Whether members need a passkey or two-step verification to reach its bases."
    )


class OrganizationChange(BaseModel):
    """Fields to store on an organization; omitted fields keep their value."""

    name: str | None = None
    logo_key: str | None = None
    new_base_access: GeneralAccess | None = None
    require_two_factor: bool | None = None


class OrganizationRecord(BaseModel):
    """A stored organization; the web app gets `OrganizationRead`."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    logo_key: str | None
    personal_of: UUID | None
    new_base_access: GeneralAccess
    require_two_factor: bool
    created_at: datetime


class OrganizationRead(BaseModel):
    """An organization as the person sees it in the rail and in its settings."""

    id: UUID = Field(description="Organization ID.")
    name: str = Field(description="Name of the organization; the web app shows its own word for a Pessoal.")
    logo_url: str | None = Field(description="The logo; null shows the initials.")
    personal: bool = Field(description="Whether this is the person's Pessoal.")
    my_role: OrgRole = Field(description="The person's role in the organization.")
    new_base_access: GeneralAccess = Field(description="The general access a new base starts with.")
    require_two_factor: bool = Field(description="Whether members need a passkey or two-step verification.")

    @classmethod
    def of(cls, organization: OrganizationRecord, my_role: OrgRole) -> Self:
        logo_url = None
        if organization.logo_key is not None:
            # The key's name changes with the logo, so a new one is never served from the browser's cache.
            logo_url = f"/v1/organizations/{organization.id}/logo?v={PurePosixPath(organization.logo_key).stem}"
        return cls(
            id=organization.id,
            name=organization.name,
            logo_url=logo_url,
            personal=organization.personal_of is not None,
            my_role=my_role,
            new_base_access=organization.new_base_access,
            require_two_factor=organization.require_two_factor,
        )


class MembershipCreate(BaseModel):
    organization_id: UUID
    account_id: UUID
    role: OrgRole


class MembershipUpdate(BaseModel):
    role: OrgRole | None = None


class MembershipRecord(MembershipCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class MemberRead(BaseModel):
    """A person with a role in an organization or in a base."""

    account_id: UUID = Field(description="Account ID.")
    name: str = Field(description="Shown name.")
    email: str = Field(description="As typed.")
    photo_url: str | None = Field(description="The photo; null shows the initials.")
    role: OrgRole | BaseRole = Field(description="Role in the organization, or in the base.")

    @classmethod
    def of(cls, account: AccountRecord, role: OrgRole | BaseRole) -> Self:
        photo_url = AccountRead.of(account).photo_url
        return cls(account_id=account.id, name=account.name, email=account.email, photo_url=photo_url, role=role)


class RoleChange(BaseModel):
    """A new role for a member of the organization."""

    role: OrgRole = Field(description="The new role.")


class BaseMemberCreate(BaseModel):
    kb_id: UUID
    account_id: UUID
    role: BaseRole


class BaseMemberUpdate(BaseModel):
    role: BaseRole | None = None


class BaseMemberRecord(BaseMemberCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class BaseMemberChange(BaseModel):
    """A new role for a person added to a base."""

    role: BaseRole = Field(description="The new role in the base.")


class BaseAccess(BaseModel):
    """Who reaches a base: everyone in its organization, and the people added to it."""

    general_access: GeneralAccess = Field(
        description="What every member of the organization gets; none for only the people added."
    )
    members: list[MemberRead] = Field(description="The people added to the base, with their base role.")


class InviteCreate(BaseModel):
    """Emails to invite, all with one role, to the organization or to one of its bases."""

    emails: list[EmailStr] = Field(min_length=1, description="Who to invite.")
    role: OrgRole | BaseRole = Field(description="An organization role, or a base role when `kb_id` is given.")
    kb_id: UUID | None = Field(default=None, description="The base to invite to; null for the organization.")


class InviteRecordCreate(BaseModel):
    organization_id: UUID
    kb_id: UUID | None
    email: str
    role: OrgRole | BaseRole
    token_hash: str
    invited_by: UUID
    expires_at: datetime


class InviteRecordUpdate(BaseModel):
    token_hash: str | None = None
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None


class InviteRecord(InviteRecordCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InviteRead(BaseModel):
    """A pending invite, as the members list shows it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Invite ID.")
    email: str = Field(description="Who was invited.")
    role: OrgRole | BaseRole = Field(description="The role they get on accepting.")
    kb_id: UUID | None = Field(description="The base invited to; null for the organization.")
    expires_at: datetime = Field(description="When the link stops working.")
    created_at: datetime = Field(description="When the invite was sent.")
