import logging
from uuid import UUID

from acervo.core.errors import ForbiddenError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.account import AccountRecord
from acervo.schemas.organization import OrganizationRecord
from acervo.services.access_service import AccessService
from acervo.services.attachment_service import attachment_key
from acervo.services.cover_service import cover_key
from acervo.services.mailer import Mailer, MailTemplate
from acervo.services.storage import Storage

logger = logging.getLogger(__name__)


class PersonalOrg(ForbiddenError):
    """A Pessoal goes only with its account."""

    code = "personal_org"


class DeletionService:
    """Deleting an organization or an account: the one place history is removed, because the whole base goes and
    never through the trash. Versions in surviving bases stay, their author left empty."""

    def __init__(self, uow: UnitOfWork, storage: Storage, mailer: Mailer, access: AccessService) -> None:
        self._uow = uow
        self._storage = storage
        self._mailer = mailer
        self._access = access

    async def delete_organization(self, actor_id: UUID, organization_id: UUID) -> None:
        """Owners only; every other member is told by email."""
        await self._access.require_org(actor_id, organization_id, "owner")
        organization = await self._uow.organizations.get(organization_id)
        if organization.personal_of is not None:
            raise PersonalOrg("a Pessoal goes only with its account", {"organization_id": str(organization_id)})
        actor = await self._uow.accounts.get(actor_id)
        mails = await self._organization_mails(organization, actor)
        keys = await self._delete(organization)
        await self._uow.commit()
        await self._remove(keys)
        await self._send(mails)

    async def delete_account(self, account_id: UUID) -> None:
        """With its Pessoal and the teams where it is the only Owner, whose members are told; "Conta excluída" is
        the last email the address gets."""
        account = await self._uow.accounts.get(account_id)
        personal = await self._uow.organizations.get_by(personal_of=account_id)
        assert personal is not None
        bases = await self._uow.kbs.count({"organization_id": personal.id})
        mails: list[tuple[AccountRecord, MailTemplate, dict[str, str]]] = []
        keys: list[str] = []
        for organization_id in await self._uow.accounts.sole_owned(account_id):
            organization = await self._uow.organizations.get(organization_id)
            mails += await self._organization_mails(organization, account)
            keys += await self._delete(organization)
        keys += await self._delete(personal)
        if account.photo_key is not None:
            keys.append(account.photo_key)
        await self._uow.accounts.delete(account_id)
        await self._uow.commit()
        await self._remove(keys)
        await self._send([*mails, (account, MailTemplate.ACCOUNT_DELETED, {"bases": str(bases)})])

    async def _organization_mails(
        self, organization: OrganizationRecord, actor: AccountRecord
    ) -> list[tuple[AccountRecord, MailTemplate, dict[str, str]]]:
        """ "Organização excluída" for every member but `actor`, read before the memberships go."""
        bases = await self._uow.kbs.count({"organization_id": organization.id})
        values = {"actor": actor.name, "organization": organization.name, "bases": str(bases)}
        return [
            (await self._uow.accounts.get(m.account_id), MailTemplate.ORG_DELETED, values)
            for m in await self._uow.memberships.of_organization(organization.id)
            if m.account_id != actor.id
        ]

    async def _delete(self, organization: OrganizationRecord) -> list[str]:
        """Deletes the rows; the stored objects they leave unused."""
        files, covers, attachments = await self._uow.organizations.delete(organization.id)
        logo = [organization.logo_key] if organization.logo_key else []
        return [*files, *map(cover_key, covers), *map(attachment_key, attachments), *logo]

    async def _remove(self, keys: list[str]) -> None:
        # After the commit: a failed delete leaves an unused object, never a row pointing at a missing one.
        for key in keys:
            try:
                await self._storage.delete(key)
            except Exception:
                logger.exception("stored object %s not deleted", key)

    async def _send(self, mails: list[tuple[AccountRecord, MailTemplate, dict[str, str]]]) -> None:
        # After the commit too: the delete is done, so a mail that fails is logged instead of answering an error.
        for account, template, values in mails:
            try:
                await self._mailer.send(account.email, template, account.language, values)
            except Exception:
                logger.exception("%s not sent to %s", template, account.id)
