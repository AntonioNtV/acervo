import builtins
from datetime import UTC, datetime
from uuid import UUID

from acervo.core.errors import AuthError, ForbiddenError, NotFoundError, ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.kb import KbCreate, KbEdit, KbRead, KbSummary, KbUpdate
from acervo.schemas.organization import (
    BaseAccess,
    BaseMemberCreate,
    BaseMemberUpdate,
    BaseRole,
    GeneralAccess,
    OrganizationRecord,
)
from acervo.services.access_service import BASE_RANK, AccessService


def _name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("a base needs a name", {"name": name})
    return name


class BaseService:
    """Knowledge bases of an organization: create, list, rename, trash, restore, and who accesses them."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._access = AccessService(uow)

    def _me(self) -> UUID:
        account_id = self._uow.account_id
        if account_id is None:
            raise AuthError("Missing or ended session.")
        return account_id

    async def _organization(self, organization_id: UUID | None) -> OrganizationRecord:
        """The organization asked for, where the account must be a member; its Pessoal when none is given."""
        me = self._me()
        if organization_id is None:
            personal = await self._uow.organizations.get_by(personal_of=me)
            if personal is None:
                raise ValidationError("a base needs an organization", {"organization_id": None})
            return personal
        await self._access.require_org(me, organization_id, "member")
        return await self._uow.organizations.get(organization_id)

    async def _shared_by(self, organization_id: UUID) -> str:
        organization = await self._uow.organizations.get(organization_id)
        if organization.personal_of is None:
            return organization.name
        return (await self._uow.accounts.get(organization.personal_of)).name

    async def _require_admin(self, kb_id: UUID, *, trashed: bool = False) -> tuple[KbRead, BaseRole]:
        kb = await self._uow.kbs.get_in(kb_id, trashed=trashed)
        return kb, await self._access.require_base(self._me(), kb_id, "admin")

    async def list(self, name: str = "", organization_id: UUID | None = None) -> builtins.list[KbSummary]:
        """The organization's bases the account can see; in its Pessoal, also those it reaches only as a guest."""
        me = self._me()
        organization = await self._organization(organization_id)
        ids = await self._access.visible_kb_ids(me, organization.id)
        shared_by: dict[UUID, str] = {}
        if organization.personal_of is not None:
            for kb_id in await self._access.visible_kb_ids(me) - ids:
                kb = await self._uow.kbs.get(kb_id)
                if await self._access.org_role(me, kb.organization_id) is None:
                    shared_by[kb_id] = await self._shared_by(kb.organization_id)
        return [
            kb.model_copy(
                update={"my_role": await self._access.base_role(me, kb.id), "shared_by": shared_by.get(kb.id)}
            )
            for kb in await self._uow.kbs.summaries(ids | shared_by.keys(), name)
        ]

    async def create(self, data: KbCreate) -> KbRead:
        """A base in `data.organization_id`, or in the acting account's Pessoal when none is given. Its creator is
        its Admin; it starts with the organization's access for new bases, none in a Pessoal."""
        organization = await self._organization(data.organization_id)
        general_access = "none" if organization.personal_of is not None else organization.new_base_access
        kb = await self._uow.kbs.create_with_admin(
            KbCreate(name=_name(data.name), description=data.description.strip(), organization_id=organization.id),
            general_access,
            self._me(),
        )
        await self._uow.commit()
        return kb.model_copy(update={"my_role": "admin"})

    async def update(self, kb_id: UUID, data: KbEdit) -> KbRead:
        _, role = await self._require_admin(kb_id)
        change = KbUpdate()
        if data.name is not None:
            change.name = _name(data.name)
        if data.description is not None:
            change.description = data.description.strip()
        if "icon" in data.model_fields_set:
            change.icon = data.icon
        kb = await self._uow.kbs.update(kb_id, change)
        await self._uow.commit()
        return kb.model_copy(update={"my_role": role})

    async def trash(self, kb_id: UUID) -> KbRead:
        """The whole base goes to the global trash; its nodes keep their own state, so it comes back intact."""
        _, role = await self._require_admin(kb_id)
        kb = await self._uow.kbs.update(kb_id, KbUpdate(deleted_at=datetime.now(UTC)))
        await self._uow.commit()
        return kb.model_copy(update={"my_role": role})

    async def trashed(self, organization_id: UUID | None = None) -> builtins.list[KbRead]:
        """The organization's bases in the trash where the account is Editor or more."""
        me = self._me()
        organization = await self._organization(organization_id)
        trashed = []
        for kb in await self._uow.kbs.trashed(await self._access.visible_kb_ids(me, organization.id)):
            role = await self._access.base_role(me, kb.id)
            if role is not None and BASE_RANK[role] >= BASE_RANK["editor"]:
                trashed.append(kb.model_copy(update={"my_role": role}))
        return trashed

    async def restore(self, kb_id: UUID) -> KbRead:
        _, role = await self._require_admin(kb_id, trashed=True)
        kb = await self._uow.kbs.update(kb_id, KbUpdate(deleted_at=None))
        await self._uow.commit()
        return kb.model_copy(update={"my_role": role})

    async def _base_access(self, kb_id: UUID) -> BaseAccess:
        kb = await self._uow.kbs.get_in(kb_id)
        return BaseAccess(general_access=kb.general_access, members=await self._uow.kbs.members(kb_id))

    async def access(self, kb_id: UUID) -> BaseAccess:
        await self._uow.kbs.get_in(kb_id)
        await self._access.require_base(self._me(), kb_id, "reader")
        return await self._base_access(kb_id)

    async def set_general_access(self, kb_id: UUID, general_access: GeneralAccess) -> BaseAccess:
        kb, _ = await self._require_admin(kb_id)
        if (await self._uow.organizations.get(kb.organization_id)).personal_of is not None:
            raise ValidationError("a Pessoal base is shared person by person", {"kb_id": str(kb_id)})
        await self._uow.kbs.set_general_access(kb_id, general_access)
        await self._uow.commit()
        return await self._base_access(kb_id)

    async def put_member(self, kb_id: UUID, account_id: UUID, role: BaseRole) -> BaseAccess:
        """Changes the base role of someone added to the base, or adds a member of its organization."""
        kb, _ = await self._require_admin(kb_id)
        added = await self._uow.base_members.get_by(kb_id=kb_id, account_id=account_id)
        if added is not None:
            await self._uow.base_members.update(added.id, BaseMemberUpdate(role=role))
        elif await self._access.org_role(account_id, kb.organization_id) is not None:
            await self._uow.base_members.create(BaseMemberCreate(kb_id=kb_id, account_id=account_id, role=role))
        else:
            # Anyone else joins a base only through an invite, which their email confirms.
            raise ForbiddenError("only members of the organization are added directly", {"account_id": str(account_id)})
        await self._uow.commit()
        return await self._base_access(kb_id)

    async def remove_member(self, kb_id: UUID, account_id: UUID) -> BaseAccess:
        await self._require_admin(kb_id)
        if await self._uow.base_members.get_by(kb_id=kb_id, account_id=account_id) is None:
            raise NotFoundError("not added to the base", {"kb_id": str(kb_id), "account_id": str(account_id)})
        await self._uow.kbs.remove_member(kb_id, account_id)
        await self._uow.commit()
        return await self._base_access(kb_id)
