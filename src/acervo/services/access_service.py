from uuid import UUID

from acervo.core.errors import ForbiddenError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.organization import BaseRole, GeneralAccess, OrgRole

ORG_RANK: dict[OrgRole, int] = {"member": 1, "admin": 2, "owner": 3}
BASE_RANK: dict[BaseRole, int] = {"reader": 1, "editor": 2, "admin": 3}


def role_in_base(added: BaseRole | None, org_role: OrgRole | None, general_access: GeneralAccess) -> BaseRole | None:
    """The highest of the base role, the general access for a member of the organization, and Admin for its
    Owners and Admins. A guest (added to the base, outside the organization) has only the base role."""
    roles: list[BaseRole] = [] if added is None else [added]
    if org_role in ("owner", "admin"):
        roles.append("admin")
    elif org_role is not None and general_access != "none":
        roles.append(general_access)
    return max(roles, key=BASE_RANK.__getitem__, default=None)


class AccessService:
    """The one rule of who may do what in an organization and in a base (spec §4), read from the database."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def org_role(self, account_id: UUID, organization_id: UUID) -> OrgRole | None:
        membership = await self._uow.memberships.get_by(organization_id=organization_id, account_id=account_id)
        return None if membership is None else membership.role

    async def base_role(self, account_id: UUID, kb_id: UUID) -> BaseRole | None:
        """The account's role in the base, by `role_in_base`."""
        kb = await self._uow.kbs.get(kb_id)
        added = await self._uow.base_members.get_by(kb_id=kb_id, account_id=account_id)
        org_role = await self.org_role(account_id, kb.organization_id)
        return role_in_base(None if added is None else added.role, org_role, kb.general_access)

    async def require_org(self, account_id: UUID, organization_id: UUID, at_least: OrgRole) -> OrgRole:
        role = await self.org_role(account_id, organization_id)
        if role is None or ORG_RANK[role] < ORG_RANK[at_least]:
            raise ForbiddenError(f"needs {at_least} in the organization", {"organization_id": str(organization_id)})
        return role

    async def require_base(self, account_id: UUID, kb_id: UUID, at_least: BaseRole) -> BaseRole:
        role = await self.base_role(account_id, kb_id)
        if role is None or BASE_RANK[role] < BASE_RANK[at_least]:
            raise ForbiddenError(f"needs {at_least} in the base", {"kb_id": str(kb_id)})
        return role

    async def visible_kb_ids(self, account_id: UUID, organization_id: UUID | None = None) -> set[UUID]:
        """Bases, live or trashed, where the account has any role; of one organization when given."""
        return await self._uow.base_members.visible_kb_ids(account_id, organization_id)
