import builtins
from datetime import UTC, datetime
from uuid import UUID

from acervo.core.errors import ValidationError
from acervo.repositories.uow import UnitOfWork
from acervo.schemas.agent import AgentCreate
from acervo.schemas.kb import KbCreate, KbEdit, KbRead, KbSummary, KbUpdate


def _name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("a base needs a name", {"name": name})
    return name


class BaseService:
    """Knowledge bases: create, list, rename, trash and restore them."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def list(self, name: str = "") -> list[KbSummary]:
        return await self._uow.kbs.summaries(name)

    async def create(self, data: KbCreate) -> KbRead:
        kb = await self._uow.kbs.create(KbCreate(name=_name(data.name), description=data.description.strip()))
        await self._uow.agents.create(AgentCreate(name="Chat do Acervo"), kb_id=kb.id, built_in=True)
        await self._uow.commit()
        return kb

    async def update(self, kb_id: UUID, data: KbEdit) -> KbRead:
        await self._uow.kbs.get_in(kb_id)
        change = KbUpdate()
        if data.name is not None:
            change.name = _name(data.name)
        if data.description is not None:
            change.description = data.description.strip()
        if "icon" in data.model_fields_set:
            change.icon = data.icon
        kb = await self._uow.kbs.update(kb_id, change)
        await self._uow.commit()
        return kb

    async def trash(self, kb_id: UUID) -> KbRead:
        """The whole base goes to the global trash; its nodes keep their own state, so it comes back intact."""
        await self._uow.kbs.get_in(kb_id)
        kb = await self._uow.kbs.update(kb_id, KbUpdate(deleted_at=datetime.now(UTC)))
        await self._uow.commit()
        return kb

    async def trashed(self) -> builtins.list[KbRead]:
        return await self._uow.kbs.trashed()

    async def restore(self, kb_id: UUID) -> KbRead:
        await self._uow.kbs.get_in(kb_id, trashed=True)
        kb = await self._uow.kbs.update(kb_id, KbUpdate(deleted_at=None))
        await self._uow.commit()
        return kb
