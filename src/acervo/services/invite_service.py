import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import get_args
from uuid import UUID

from pydantic import BaseModel, Field

from acervo.core.errors import (
    AlreadyMember,
    CodeInvalid,
    InviteMismatch,
    NotFoundError,
    TooManyAttempts,
    ValidationError,
)
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRecord
from acervo.schemas.organization import (
    BaseMemberCreate,
    BaseMemberUpdate,
    BaseRole,
    InviteCreate,
    InviteRead,
    InviteRecord,
    InviteRecordCreate,
    InviteRecordUpdate,
    MembershipCreate,
    OrgRole,
)
from acervo.services.access_service import BASE_RANK, AccessService
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.session_service import token_hash

INVITE_TTL = timedelta(days=7)
RESEND_AFTER = timedelta(seconds=60)
MEMBERS_PATH = "/organizacao/membros"


def _now() -> datetime:
    return datetime.now(UTC)


class InvitePreview(BaseModel):
    """An invite as the Convite screen shows it, before anyone signs in."""

    organization_id: UUID = Field(description="The organization invited to, or the one of the base.")
    kb_id: UUID | None = Field(description="The base invited to; null for the organization.")
    organization: str = Field(description="Name of the organization.")
    base: str | None = Field(description="Name of the base; null for an organization invite.")
    inviter: str = Field(description="Name of who invited.")
    role: OrgRole | BaseRole = Field(description="The role the invite gives.")
    email: str = Field(description="Who the invite is for; the token was mailed to it, and Criar conta fills it in.")
    expired: bool = Field(description="Whether the link stopped working.")


class InviteService:
    """Invites to an organization or to a base: send, resend, revoke, accept."""

    def __init__(
        self, uow: UnitOfWork, mailer: Mailer, access: AccessService, now: Callable[[], datetime] = _now
    ) -> None:
        self._uow = uow
        self._mailer = mailer
        self._access = access
        self._now = now

    async def invite_to_organization(
        self, account_id: UUID, organization_id: UUID, data: InviteCreate
    ) -> list[InviteRead]:
        """Invites each email to the team; a live invite of the same email is sent again. Only an Owner invites
        Owners. Refused with `already_member` when any email is already in the organization."""
        if data.role not in get_args(OrgRole) or data.kb_id is not None:
            raise ValidationError("not an organization role, or a base invite", {"role": data.role})
        await self._access.require_org(account_id, organization_id, "owner" if data.role == "owner" else "admin")
        organization = await self._uow.organizations.get(organization_id)
        if organization.personal_of is not None:
            raise ValidationError("a Pessoal has no members", {"organization_id": str(organization_id)})
        emails = _unique(data.emails)
        members = []
        for email in emails:
            person = await self._uow.accounts.by_email(email)
            if person is not None and await self._access.org_role(person.id, organization_id) is not None:
                members.append(email)
        if members:
            raise AlreadyMember("already in the organization", {"emails": members})
        issued = [await self._issue(account_id, organization_id, None, email, data.role) for email in emails]
        await self._uow.commit()
        for invite, token in issued:
            if token is not None:
                await self._send_invite(invite, token)
        return [InviteRead.model_validate(invite) for invite, _ in issued]

    async def invite_to_base(self, account_id: UUID, kb_id: UUID, data: InviteCreate) -> list[InviteRead]:
        """Adds the members of the base's organization at once (they get `base_shared`) and invites anyone else
        as a guest of the base; gives the invites."""
        if data.role not in get_args(BaseRole):
            raise ValidationError("not a base role", {"role": data.role})
        await self._access.require_base(account_id, kb_id, "admin")
        kb = await self._uow.kbs.get_in(kb_id)
        added: list[AccountRecord] = []
        issued: list[tuple[InviteRecord, str | None]] = []
        for email in _unique(data.emails):
            person = await self._uow.accounts.by_email(email)
            if person is not None and await self._access.org_role(person.id, kb.organization_id) is not None:
                await self._add_to_base(kb_id, person.id, data.role)  # type: ignore[arg-type]
                added.append(person)
            else:
                issued.append(await self._issue(account_id, kb.organization_id, kb_id, email, data.role))
        await self._uow.commit()
        inviter = await self._uow.accounts.get(account_id)
        for person in added:
            values = {"inviter": inviter.name, "base": kb.name, "role": data.role, "link": f"/kbs/{kb_id}"}
            await self._mailer.send(person.email, MailTemplate.BASE_SHARED, person.language, values)
        for invite, token in issued:
            if token is not None:
                await self._send_invite(invite, token)
        return [InviteRead.model_validate(invite) for invite, _ in issued]

    async def pending_for_organization(self, account_id: UUID, organization_id: UUID) -> list[InviteRead]:
        await self._access.require_org(account_id, organization_id, "admin")
        return [InviteRead.model_validate(i) for i in await self._uow.invites.pending(organization_id, None)]

    async def pending_for_base(self, account_id: UUID, kb_id: UUID) -> list[InviteRead]:
        await self._access.require_base(account_id, kb_id, "admin")
        kb = await self._uow.kbs.get_in(kb_id)
        return [InviteRead.model_validate(i) for i in await self._uow.invites.pending(kb.organization_id, kb_id)]

    async def resend(self, account_id: UUID, invite_id: UUID) -> InviteRead:
        """A new link valid for 7 days, the old one no longer valid; at most once a minute."""
        invite = await self._pending(account_id, invite_id)
        if self._sent_recently(invite):
            raise TooManyAttempts("the invite was sent less than a minute ago")
        invite, token = await self._renew(invite)
        await self._uow.commit()
        await self._send_invite(invite, token)
        return InviteRead.model_validate(invite)

    async def revoke(self, account_id: UUID, invite_id: UUID) -> None:
        invite = await self._pending(account_id, invite_id)
        await self._uow.invites.update(invite.id, InviteRecordUpdate(revoked_at=self._now()))
        await self._uow.commit()

    async def preview(self, token: str) -> InvitePreview:
        """The invite of a link, for anyone holding it; a revoked or accepted one is `code_invalid`."""
        invite = await self._uow.invites.get_by(token_hash=token_hash(token))
        if invite is None or invite.accepted_at is not None or invite.revoked_at is not None:
            raise CodeInvalid("wrong, revoked or used invite")
        return await self._preview(invite)

    async def accept(self, account_id: UUID, token: str) -> InvitePreview:
        """Joins the organization, or the base as its guest, with the invite's role; the email must be the
        account's. A used invite answers again for the account it is for while that account is still in, so a
        link opened after signing up (which already joined) lands where it leads."""
        invite = await self._uow.invites.by_token(token_hash(token))
        account = await self._uow.accounts.get(account_id)
        if invite is not None and invite.accepted_at is not None and await self._joined(invite, account):
            return await self._preview(invite)
        if (
            invite is None
            or invite.accepted_at is not None
            or invite.revoked_at is not None
            or invite.expires_at <= self._now()
        ):
            raise CodeInvalid("wrong, expired, revoked or used invite")
        if invite.email.lower() != account.email.lower():
            raise InviteMismatch("the invite is for another email", {"email": invite.email})
        await self._join(invite, account_id)
        await self._uow.commit()
        await self._send_accepted(invite, account)
        return await self._preview(invite)

    async def claim(self, account_id: UUID) -> None:
        """Accepts every live invite of the account's email, once the email was just confirmed."""
        # Signing in has no session yet: the bases joined are read back as the account that joined them.
        self._uow.act_as(account_id)
        account = await self._uow.accounts.get(account_id)
        invites = await self._uow.invites.claimable(account.email, self._now())
        for invite in invites:
            await self._join(invite, account_id)
        await self._uow.commit()
        for invite in invites:
            await self._send_accepted(invite, account)

    async def _issue(
        self, inviter_id: UUID, organization_id: UUID, kb_id: UUID | None, email: str, role: OrgRole | BaseRole
    ) -> tuple[InviteRecord, str | None]:
        """The invite of this email to this target, made or renewed; with the token to mail, None when it was sent
        less than a minute ago. A live one with another role is revoked for the new one."""
        now = self._now()
        for live in await self._uow.invites.pending(organization_id, kb_id, email):
            if live.role != role:
                await self._uow.invites.update(live.id, InviteRecordUpdate(revoked_at=now))
            elif self._sent_recently(live):
                return live, None
            else:
                return await self._renew(live)
        token = secrets.token_urlsafe(32)
        invite = InviteRecordCreate(
            organization_id=organization_id,
            kb_id=kb_id,
            email=email,
            role=role,
            token_hash=token_hash(token),
            invited_by=inviter_id,
            expires_at=now + INVITE_TTL,
        )
        return await self._uow.invites.create(invite, created_at=now), token

    async def _renew(self, invite: InviteRecord) -> tuple[InviteRecord, str]:
        token = secrets.token_urlsafe(32)
        renewal = InviteRecordUpdate(token_hash=token_hash(token), expires_at=self._now() + INVITE_TTL)
        return await self._uow.invites.update(invite.id, renewal), token

    def _sent_recently(self, invite: InviteRecord) -> bool:
        # Every send sets the expiry a TTL ahead, so the expiry tells when the last one went out.
        return self._now() < invite.expires_at - INVITE_TTL + RESEND_AFTER

    async def _pending(self, account_id: UUID, invite_id: UUID) -> InviteRecord:
        """The invite, not accepted nor revoked, when the account may manage it."""
        invite = await self._uow.invites.get(invite_id)
        if invite.accepted_at is not None or invite.revoked_at is not None:
            raise NotFoundError(f"invite {invite_id} not found", {"id": str(invite_id)})
        if invite.kb_id is None:
            await self._access.require_org(account_id, invite.organization_id, "admin")
        else:
            await self._access.require_base(account_id, invite.kb_id, "admin")
        return invite

    async def _join(self, invite: InviteRecord, account_id: UUID) -> None:
        if invite.kb_id is not None:
            await self._add_to_base(invite.kb_id, account_id, invite.role)  # type: ignore[arg-type]
        elif await self._access.org_role(account_id, invite.organization_id) is None:
            membership = MembershipCreate(
                organization_id=invite.organization_id,
                account_id=account_id,
                role=invite.role,  # type: ignore[arg-type]
            )
            await self._uow.memberships.create(membership)
        await self._uow.invites.update(invite.id, InviteRecordUpdate(accepted_at=self._now()))

    async def _joined(self, invite: InviteRecord, account: AccountRecord) -> bool:
        """Whether the invite is this account's and the account still holds what it gave."""
        if invite.email.lower() != account.email.lower():
            return False
        if invite.kb_id is not None:
            return await self._access.base_role(account.id, invite.kb_id) is not None
        return await self._access.org_role(account.id, invite.organization_id) is not None

    async def _add_to_base(self, kb_id: UUID, account_id: UUID, role: BaseRole) -> None:
        """Gives the role in the base, keeping a higher one the person already has there."""
        added = await self._uow.base_members.get_by(kb_id=kb_id, account_id=account_id)
        if added is None:
            await self._uow.base_members.create(BaseMemberCreate(kb_id=kb_id, account_id=account_id, role=role))
        elif BASE_RANK[added.role] < BASE_RANK[role]:
            await self._uow.base_members.update(added.id, BaseMemberUpdate(role=role))

    async def _target_name(self, invite: InviteRecord) -> str:
        """The base for a base invite, else the organization: what the emails say the person joins."""
        if invite.kb_id is not None:
            return (await self._uow.kbs.get(invite.kb_id)).name
        return (await self._uow.organizations.get(invite.organization_id)).name

    async def _send_invite(self, invite: InviteRecord, token: str) -> None:
        inviter = await self._uow.accounts.get(invite.invited_by)
        person = await self._uow.accounts.by_email(invite.email)
        if invite.kb_id is not None:
            bases = [(await self._uow.kbs.get(invite.kb_id)).name]
        else:
            bases = await self._uow.invites.base_names(invite.organization_id, invite.role)  # type: ignore[arg-type]
        values = {
            "inviter": inviter.name,
            "organization": await self._target_name(invite),
            "role": invite.role,
            "bases": "\n".join(bases),
            "expires_at": invite.expires_at.isoformat(),
            "link": token,
        }
        language = "pt-BR" if person is None else person.language
        await self._mailer.send(invite.email, MailTemplate.ORG_INVITE, language, values)

    async def _send_accepted(self, invite: InviteRecord, member: AccountRecord) -> None:
        inviter = await self._uow.accounts.get(invite.invited_by)
        values = {
            "name": member.name,
            "member_email": member.email,
            "organization": await self._target_name(invite),
            "role": invite.role,
            # The organization rides along: the settings show the one this browser has open, maybe another.
            "link": f"{MEMBERS_PATH}?org={invite.organization_id}" if invite.kb_id is None else f"/kbs/{invite.kb_id}",
        }
        await self._mailer.send(inviter.email, MailTemplate.INVITE_ACCEPTED, inviter.language, values)

    async def _preview(self, invite: InviteRecord) -> InvitePreview:
        organization = await self._uow.organizations.get(invite.organization_id)
        base = None if invite.kb_id is None else await self._uow.invites.base_name(invite.token_hash)
        return InvitePreview(
            organization_id=organization.id,
            kb_id=invite.kb_id,
            organization=organization.name,
            base=base,
            inviter=(await self._uow.accounts.get(invite.invited_by)).name,
            role=invite.role,
            email=invite.email,
            expired=invite.expires_at <= self._now(),
        )


def _unique(emails: list[str]) -> list[str]:
    """Each email once, ignoring case, as first typed."""
    unique: dict[str, str] = {}
    for email in emails:
        unique.setdefault(email.lower(), email)
    return list(unique.values())
